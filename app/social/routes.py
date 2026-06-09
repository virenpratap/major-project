from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.social import bp
from app.extensions import db
from app.models import Post, PostLike, Comment, PostTag, Tag, Connection, Follow, User, Profile, UserTag
from datetime import datetime, timezone, timedelta
import math


@bp.route('/feed')
@login_required
def feed():
    return render_template('social/feed.html')


@bp.route('/api/posts', methods=['POST'])
@login_required
def create_post():
    data = request.get_json()
    if not data or not data.get('content', '').strip():
        return jsonify({'error': 'Content is required'}), 400

    content = data['content'].strip()
    scope = data.get('scope', 'global')  # global or department

    post = Post(author_id=current_user.id, content=content, scope=scope)

    # Auto-set department for department-scoped posts
    if scope == 'department' and current_user.profile and current_user.profile.department_id:
        post.department_id = current_user.profile.department_id
    elif scope == 'department':
        # Fallback to global if user has no department
        post.scope = 'global'

    db.session.add(post)
    db.session.flush()

    # Extract hashtags
    import re
    hashtags = re.findall(r'#(\w+)', content)
    for tag_name in hashtags:
        tag_name = tag_name.lower()
        tag = Tag.query.filter_by(name=tag_name, type='hashtag').first()
        if not tag:
            tag = Tag(name=tag_name, type='hashtag', usage_count=1)
            db.session.add(tag)
            db.session.flush()
        else:
            tag.usage_count += 1
        pt = PostTag(post_id=post.id, tag_id=tag.id)
        db.session.add(pt)

    db.session.commit()

    # Publish event
    try:
        from core.event_bus import publish
        publish('post_created', {'post_id': post.id, 'author_id': current_user.id})
    except Exception:
        pass

    return jsonify(_serialize_post(post)), 201


@bp.route('/api/feed')
@login_required
def get_feed():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    scope = request.args.get('scope', 'global')  # global or department

    # Get posts with ranking
    posts = _get_ranked_feed(current_user.id, page, per_page, scope)
    return jsonify({
        'posts': [_serialize_post(p) for p in posts],
        'page': page,
        'scope': scope,
        'has_more': len(posts) == per_page
    })


@bp.route('/api/posts/<int:post_id>/like', methods=['POST'])
@login_required
def toggle_like(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    existing = PostLike.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'liked': False, 'count': post.like_count})
    else:
        like = PostLike(post_id=post_id, user_id=current_user.id)
        db.session.add(like)
        db.session.commit()
        return jsonify({'liked': True, 'count': post.like_count})


@bp.route('/api/posts/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    data = request.get_json()
    if not data or not data.get('content', '').strip():
        return jsonify({'error': 'Content is required'}), 400

    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        parent_id=data.get('parent_id'),
        content=data['content'].strip()
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify({
        'id': comment.id,
        'content': comment.content,
        'author': comment.author.username,
        'author_id': comment.user_id,
        'parent_id': comment.parent_id,
        'created_at': comment.created_at.isoformat(),
        'avatar': comment.author.profile.full_name[0].upper() if comment.author.profile and comment.author.profile.full_name else comment.author.username[0].upper()
    }), 201


@bp.route('/api/posts/<int:post_id>/comments')
@login_required
def get_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    result = []
    for c in comments:
        result.append({
            'id': c.id,
            'content': c.content,
            'author': c.author.username,
            'author_id': c.user_id,
            'parent_id': c.parent_id,
            'created_at': c.created_at.isoformat(),
            'avatar': c.author.profile.full_name[0].upper() if c.author.profile and c.author.profile.full_name else c.author.username[0].upper()
        })
    return jsonify(result)


@bp.route('/api/connections/request', methods=['POST'])
@login_required
def connection_request():
    data = request.get_json()
    target_id = data.get('target_id')
    if not target_id or target_id == current_user.id:
        return jsonify({'error': 'Invalid target'}), 400

    existing = Connection.query.filter(
        ((Connection.user_id == current_user.id) & (Connection.target_id == target_id)) |
        ((Connection.user_id == target_id) & (Connection.target_id == current_user.id))
    ).first()

    if existing:
        return jsonify({'error': 'Connection already exists', 'status': existing.status}), 400

    conn = Connection(user_id=current_user.id, target_id=target_id, status='pending')
    db.session.add(conn)
    db.session.commit()

    return jsonify({'status': 'pending', 'id': conn.id}), 201


@bp.route('/api/connections/respond', methods=['POST'])
@login_required
def connection_respond():
    data = request.get_json()
    conn_id = data.get('connection_id')
    action = data.get('action')  # accept or reject

    conn = db.session.get(Connection, conn_id)
    if not conn or conn.target_id != current_user.id:
        return jsonify({'error': 'Connection not found'}), 404

    if action == 'accept':
        conn.status = 'accepted'
    elif action == 'reject':
        conn.status = 'rejected'
    else:
        return jsonify({'error': 'Invalid action'}), 400

    db.session.commit()
    return jsonify({'status': conn.status})


@bp.route('/api/follow/<int:user_id>', methods=['POST'])
@login_required
def toggle_follow(user_id):
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot follow yourself'}), 400

    existing = Follow.query.filter_by(follower_id=current_user.id, followee_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'following': False})
    else:
        follow = Follow(follower_id=current_user.id, followee_id=user_id)
        db.session.add(follow)
        db.session.commit()
        return jsonify({'following': True})


# ─────────────────── FEED RANKING HELPERS ───────────────────

def _get_ranked_feed(user_id, page, per_page, scope='global'):
    """Get posts ranked by relevance, connection strength, recency, and engagement."""
    # Get all recent posts (last 30 days for efficiency)
    now = datetime.utcnow()
    cutoff = now - timedelta(days=30)

    try:
        query = Post.query.filter(Post.created_at >= cutoff)
        if scope == 'department':
            # Filter to user's department only
            from app.models import Profile
            user_profile = Profile.query.filter_by(user_id=user_id).first()
            if user_profile and user_profile.department_id:
                query = query.filter(
                    (Post.scope == 'department') & (Post.department_id == user_profile.department_id)
                )
            else:
                query = query.filter(Post.scope == 'global')
        posts = query.all()
    except Exception:
        posts = []

    if not posts:
        # Fallback to latest posts overall
        posts = Post.query.order_by(Post.created_at.desc()).limit(per_page * 3).all()

    if not posts:
        return []

    # Get user's connections and tags for scoring
    connected_ids = set()
    try:
        connections = Connection.query.filter(
            ((Connection.user_id == user_id) | (Connection.target_id == user_id)),
            Connection.status == 'accepted'
        ).all()
        for c in connections:
            connected_ids.add(c.user_id if c.target_id == user_id else c.target_id)
    except Exception:
        pass

    followed_ids = set()
    try:
        followed_ids = set(f.followee_id for f in Follow.query.filter_by(follower_id=user_id).all())
    except Exception:
        pass

    user_tag_ids = set()
    try:
        user_tag_ids = set(ut.tag_id for ut in UserTag.query.filter_by(user_id=user_id).all())
    except Exception:
        pass

    # Score each post
    scored = []
    for post in posts:
        try:
            if post.author_id == user_id:
                # Own posts get moderate priority
                score = 0.5
            else:
                # Relevance: tag overlap
                post_tag_ids = set(pt.tag_id for pt in PostTag.query.filter_by(post_id=post.id).all())
                tag_overlap = len(user_tag_ids & post_tag_ids) / max(len(user_tag_ids | post_tag_ids), 1)
                relevance = tag_overlap

                # Connection strength
                conn_score = 0
                if post.author_id in connected_ids:
                    conn_score = 1.0
                elif post.author_id in followed_ids:
                    conn_score = 0.5

                # Recency decay (exponential)
                post_time = post.created_at if post.created_at else now
                age_hours = max((now - post_time).total_seconds() / 3600, 0.1)
                recency = math.exp(-0.05 * age_hours)

                # Engagement
                like_count = post.like_count if hasattr(post, 'like_count') else 0
                comment_count = post.comment_count if hasattr(post, 'comment_count') else 0
                engagement = min((like_count + comment_count * 2) / 50, 1.0)

                score = (0.4 * relevance + 0.3 * conn_score + 0.2 * recency + 0.1 * engagement)

            scored.append((score, post))
        except Exception:
            scored.append((0, post))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    return [p for _, p in scored[start:end]]


def _serialize_post(post):
    """Serialize a post for JSON response."""
    from flask_login import current_user
    liked = PostLike.query.filter_by(post_id=post.id, user_id=current_user.id).first() is not None

    author_profile = post.author.profile
    avatar_letter = ''
    if author_profile and author_profile.full_name:
        avatar_letter = author_profile.full_name[0].upper()
    else:
        avatar_letter = post.author.username[0].upper()

    return {
        'id': post.id,
        'content': post.content,
        'author': post.author.username,
        'author_id': post.author_id,
        'author_role': post.author.role,
        'author_name': author_profile.full_name if author_profile else post.author.username,
        'author_title': author_profile.title if author_profile else '',
        'avatar_letter': avatar_letter,
        'avatar_url': author_profile.avatar_url if author_profile and author_profile.avatar_url else '',
        'scope': post.scope,
        'department': post.department.name if post.department else '',
        'like_count': post.like_count,
        'comment_count': post.comment_count,
        'liked': liked,
        'created_at': post.created_at.isoformat(),
    }

from flask import request, jsonify
from flask_login import login_required, current_user
from app.api import bp
from app.extensions import db
from app.models import Tag, Notification, User, Profile


@bp.route('/suggest')
@login_required
def suggest():
    """Autocomplete/typeahead for skills, companies, colleges, etc."""
    q = request.args.get('q', '').strip()
    tag_type = request.args.get('type', 'skill')
    limit = request.args.get('limit', 8, type=int)

    if not q or len(q) < 1:
        return jsonify([])

    tags = Tag.query.filter(
        Tag.type == tag_type,
        Tag.name.ilike(f'{q}%')
    ).order_by(Tag.usage_count.desc()).limit(limit).all()

    return jsonify([{
        'id': t.id,
        'name': t.name,
        'type': t.type,
        'usage_count': t.usage_count
    } for t in tags])


@bp.route('/notifications')
@login_required
def get_notifications():
    """Get recent notifications (fallback polling)."""
    unread_only = request.args.get('unread', 'true') == 'true'

    query = Notification.query.filter_by(user_id=current_user.id)
    if unread_only:
        query = query.filter_by(is_read=False)

    notifications = query.order_by(Notification.created_at.desc()).limit(20).all()

    return jsonify([{
        'id': n.id,
        'type': n.type,
        'data': n.data,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat()
    } for n in notifications])


@bp.route('/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    data = request.get_json()
    notification_ids = data.get('ids', [])

    if notification_ids:
        Notification.query.filter(
            Notification.id.in_(notification_ids),
            Notification.user_id == current_user.id
        ).update({Notification.is_read: True}, synchronize_session=False)
    else:
        # Mark all as read
        Notification.query.filter_by(
            user_id=current_user.id, is_read=False
        ).update({Notification.is_read: True}, synchronize_session=False)

    db.session.commit()
    return jsonify({'message': 'Marked as read'})


@bp.route('/notifications/count')
@login_required
def notification_count():
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    return jsonify({'count': count})


@bp.route('/search/users')
@login_required
def search_users():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    users = User.query.join(Profile).filter(
        User.is_active == True,
        (User.username.ilike(f'%{q}%') | Profile.full_name.ilike(f'%{q}%'))
    ).limit(10).all()

    return jsonify([{
        'id': u.id,
        'username': u.username,
        'name': u.profile.full_name if u.profile else u.username,
        'role': u.role,
        'title': u.profile.title if u.profile else '',
        'avatar': (u.profile.full_name[0].upper() if u.profile and u.profile.full_name else u.username[0].upper())
    } for u in users])

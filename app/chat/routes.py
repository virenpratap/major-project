from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.chat import bp
from app.extensions import db
from app.models import Message, ChatGroup, ChatGroupMember, User


@bp.route('/')
@login_required
def inbox():
    return render_template('chat/inbox.html')


@bp.route('/room/<room_id>')
@login_required
def room(room_id):
    return render_template('chat/room.html', room_id=room_id)


@bp.route('/api/conversations')
@login_required
def get_conversations():
    """Get all conversations for current user."""
    # Get DM rooms
    dm_messages = db.session.query(Message.room).filter(
        Message.room.like('dm_%'),
        Message.room.contains(str(current_user.id))
    ).distinct().all()

    conversations = []
    for (room,) in dm_messages:
        # Parse other user from room name
        parts = room.split('_')
        if len(parts) == 3:
            user_ids = [int(parts[1]), int(parts[2])]
            other_id = user_ids[0] if user_ids[1] == current_user.id else user_ids[1]
            other_user = db.session.get(User, other_id)

            # Get last message
            last_msg = Message.query.filter_by(room=room).order_by(
                Message.created_at.desc()
            ).first()

            unread = Message.query.filter_by(
                room=room, is_read=False
            ).filter(Message.sender_id != current_user.id).count()

            if other_user:
                conversations.append({
                    'room': room,
                    'type': 'dm',
                    'name': other_user.profile.full_name if other_user.profile else other_user.username,
                    'avatar': (other_user.profile.full_name[0].upper() if other_user.profile and other_user.profile.full_name else other_user.username[0].upper()),
                    'last_message': last_msg.content[:50] if last_msg else '',
                    'last_time': last_msg.created_at.isoformat() if last_msg else '',
                    'unread': unread
                })

    # Get group rooms
    group_memberships = ChatGroupMember.query.filter_by(user_id=current_user.id).all()
    for membership in group_memberships:
        group = membership.group
        room = f'grp_{group.id}'

        last_msg = Message.query.filter_by(room=room).order_by(
            Message.created_at.desc()
        ).first()

        unread = Message.query.filter_by(
            room=room, is_read=False
        ).filter(Message.sender_id != current_user.id).count()

        conversations.append({
            'room': room,
            'type': 'group',
            'name': group.name,
            'avatar': group.name[0].upper(),
            'last_message': last_msg.content[:50] if last_msg else '',
            'last_time': last_msg.created_at.isoformat() if last_msg else '',
            'unread': unread,
            'members_count': len(group.members)
        })

    # Sort by last message time
    conversations.sort(key=lambda x: x.get('last_time', ''), reverse=True)
    return jsonify(conversations)


@bp.route('/api/history/<room_id>')
@login_required
def get_history(room_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    messages = Message.query.filter_by(room=room_id).order_by(
        Message.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    result = [{
        'id': m.id,
        'content': m.content,
        'sender_id': m.sender_id,
        'sender_name': m.sender.profile.full_name if m.sender.profile else m.sender.username,
        'sender_avatar': (m.sender.profile.full_name[0].upper() if m.sender.profile and m.sender.profile.full_name else m.sender.username[0].upper()),
        'is_mine': m.sender_id == current_user.id,
        'is_read': m.is_read,
        'created_at': m.created_at.isoformat()
    } for m in reversed(messages.items)]

    return jsonify({
        'messages': result,
        'has_more': messages.has_next,
        'page': page
    })


@bp.route('/api/dm/<int:user_id>')
@login_required
def get_or_create_dm(user_id):
    """Get or create DM room with a user."""
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot message yourself'}), 400

    other_user = db.session.get(User, user_id)
    if not other_user:
        return jsonify({'error': 'User not found'}), 404

    min_id = min(current_user.id, user_id)
    max_id = max(current_user.id, user_id)
    room = f'dm_{min_id}_{max_id}'

    return jsonify({
        'room': room,
        'name': other_user.profile.full_name if other_user.profile else other_user.username
    })


@bp.route('/api/groups', methods=['POST'])
@login_required
def create_group():
    data = request.get_json()
    name = data.get('name', '').strip()
    member_ids = data.get('members', [])

    if not name:
        return jsonify({'error': 'Group name required'}), 400

    group = ChatGroup(name=name, created_by=current_user.id)
    db.session.add(group)
    db.session.flush()

    # Add creator as member
    db.session.add(ChatGroupMember(group_id=group.id, user_id=current_user.id))

    # Add other members
    for uid in member_ids:
        if uid != current_user.id:
            db.session.add(ChatGroupMember(group_id=group.id, user_id=uid))

    db.session.commit()

    return jsonify({
        'room': f'grp_{group.id}',
        'name': group.name,
        'id': group.id
    }), 201

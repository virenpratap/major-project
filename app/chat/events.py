"""
WebSocket event handlers for real-time chat.
"""
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app.extensions import socketio, db
from app.models import Message
from datetime import datetime, timezone


@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        # Join personal notification room
        join_room(f'user_{current_user.id}')
        emit('connected', {'user_id': current_user.id})


@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')


@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    if room and current_user.is_authenticated:
        join_room(room)
        emit('user_joined', {
            'user_id': current_user.id,
            'username': current_user.username
        }, room=room)


@socketio.on('leave_room')
def handle_leave_room(data):
    room = data.get('room')
    if room:
        leave_room(room)
        emit('user_left', {
            'user_id': current_user.id,
            'username': current_user.username
        }, room=room)


@socketio.on('send_message')
def handle_send_message(data):
    room = data.get('room')
    content = data.get('message', '').strip()

    if not room or not content or not current_user.is_authenticated:
        return

    # Save message to DB
    msg = Message(
        room=room,
        sender_id=current_user.id,
        content=content
    )
    db.session.add(msg)
    db.session.commit()

    sender_name = current_user.profile.full_name if current_user.profile and current_user.profile.full_name else current_user.username
    avatar = sender_name[0].upper()

    # Broadcast to room
    emit('new_message', {
        'id': msg.id,
        'content': content,
        'sender_id': current_user.id,
        'sender_name': sender_name,
        'sender_avatar': avatar,
        'room': room,
        'created_at': msg.created_at.isoformat()
    }, room=room)

    # Acknowledge to sender
    emit('message_ack', {
        'id': msg.id,
        'room': room,
        'status': 'delivered'
    })


@socketio.on('typing')
def handle_typing(data):
    room = data.get('room')
    if room and current_user.is_authenticated:
        emit('user_typing', {
            'user_id': current_user.id,
            'username': current_user.username,
            'room': room
        }, room=room, include_self=False)


@socketio.on('stop_typing')
def handle_stop_typing(data):
    room = data.get('room')
    if room and current_user.is_authenticated:
        emit('user_stop_typing', {
            'user_id': current_user.id,
            'room': room
        }, room=room, include_self=False)


@socketio.on('read_receipt')
def handle_read_receipt(data):
    room = data.get('room')
    message_ids = data.get('message_ids', [])

    if room and message_ids and current_user.is_authenticated:
        # Mark messages as read
        Message.query.filter(
            Message.id.in_(message_ids),
            Message.room == room,
            Message.sender_id != current_user.id
        ).update({Message.is_read: True}, synchronize_session=False)
        db.session.commit()

        emit('messages_read', {
            'room': room,
            'message_ids': message_ids,
            'reader_id': current_user.id
        }, room=room, include_self=False)

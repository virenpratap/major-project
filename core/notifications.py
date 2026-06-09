"""
Notification dispatcher - WebSocket push with DB fallback.
"""
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def send_notification(user_id, notif_type, data, save=True):
    """Send a notification via WebSocket and optionally save to DB."""
    # Save to database
    if save:
        try:
            from app.extensions import db
            from app.models import Notification
            notif = Notification(
                user_id=user_id,
                type=notif_type,
                data=json.dumps(data) if isinstance(data, dict) else str(data)
            )
            db.session.add(notif)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to save notification: {e}")

    # Push via WebSocket
    try:
        from app.extensions import socketio
        socketio.emit('notification', {
            'type': notif_type,
            'data': data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, room=f'user_{user_id}')
    except Exception as e:
        logger.error(f"Failed to push notification: {e}")


def notify_resume_ready(user_id, resume_id, score):
    """Notify user that resume analysis is complete."""
    send_notification(user_id, 'resume_ready', {
        'resume_id': resume_id,
        'score': score,
        'message': f'Your resume has been analyzed! Score: {score}/100'
    })


def notify_new_message(payload):
    """Notify user of a new chat message."""
    send_notification(payload.get('recipient_id'), 'new_message', {
        'room': payload.get('room'),
        'sender': payload.get('sender_name'),
        'preview': payload.get('content', '')[:100]
    })


def notify_referral_update(user_id, referral_id, status):
    """Notify user of referral status change."""
    send_notification(user_id, 'referral_update', {
        'referral_id': referral_id,
        'status': status,
        'message': f'Your referral status has been updated to: {status}'
    })


def notify_connection_request(user_id, requester_name):
    """Notify user of a new connection request."""
    send_notification(user_id, 'connection_request', {
        'from': requester_name,
        'message': f'{requester_name} sent you a connection request'
    })
def get_notifications(user_id, limit=10, unread_only=False):
    """Retrieve notifications for a user."""
    from app.models import Notification
    query = Notification.query.filter_by(user_id=user_id)
    if unread_only:
        query = query.filter_by(is_read=False)
    return query.order_by(Notification.created_at.desc()).limit(limit).all()

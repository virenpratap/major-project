"""
SNS/SQS-style event bus using Python's queue.Queue.
Supports publish/subscribe pattern with persistent job tracking.
"""
from queue import Queue
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger(__name__)

# Global event queue
event_queue = Queue()

# Handler registry
_handlers = {}


def publish(event_type, payload):
    """Publish an event to the event bus."""
    event = {
        'type': event_type,
        'data': payload,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    event_queue.put(event)
    logger.info(f"Event published: {event_type}")

    # Persist critical events to DB
    _persist_event(event_type, payload)


def subscribe(event_type, handler):
    """Register a handler for an event type."""
    if event_type not in _handlers:
        _handlers[event_type] = []
    _handlers[event_type].append(handler)
    logger.info(f"Handler registered for: {event_type}")


def get_handlers(event_type):
    """Get all handlers for an event type."""
    return _handlers.get(event_type, [])


def _persist_event(event_type, payload):
    """Persist critical events to the jobs_queue table for reliability."""
    critical_events = {
        'resume_uploaded', 'resume_processed',
        'referral_requested', 'candidates_ranked',
        'profile_updated'
    }
    if event_type in critical_events:
        try:
            from app.extensions import db
            from app.models import JobQueue
            job = JobQueue(
                event_type=event_type,
                payload=json.dumps(payload),
                status='pending'
            )
            db.session.add(job)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to persist event {event_type}: {e}")


# Event types
class EventType:
    RESUME_UPLOADED = 'resume_uploaded'
    RESUME_PROCESSED = 'resume_processed'
    REFERRAL_REQUESTED = 'referral_requested'
    CANDIDATES_RANKED = 'candidates_ranked'
    PROFILE_UPDATED = 'profile_updated'
    POST_CREATED = 'post_created'
    MESSAGE_SENT = 'message_sent'

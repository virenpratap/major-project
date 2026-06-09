"""
Background worker threads for processing events from the event bus.
Runs as daemon threads on application start.
"""
import threading
import logging
import json
from core.event_bus import event_queue, get_handlers

logger = logging.getLogger(__name__)

_app = None
_workers_started = False


def start_workers(app, num_workers=3):
    """Start background worker threads."""
    global _app, _workers_started
    if _workers_started:
        return

    _app = app
    _workers_started = True

    for i in range(num_workers):
        t = threading.Thread(target=_worker_loop, args=(i,), daemon=True)
        t.name = f"EventWorker-{i}"
        t.start()
        logger.info(f"Started worker thread: EventWorker-{i}")


def _worker_loop(worker_id):
    """Main worker loop: consume events from the queue and dispatch to handlers."""
    while True:
        try:
            event = event_queue.get(timeout=5)
        except Exception:
            # Queue.get timeout — just loop
            continue

        event_type = event.get('type')
        payload = event.get('data', {})

        logger.info(f"Worker-{worker_id} processing: {event_type}")

        # Get registered handlers
        handlers = get_handlers(event_type)

        if not handlers:
            # Use default handler dispatch
            _default_dispatch(event_type, payload)
        else:
            for handler in handlers:
                _execute_handler(handler, event_type, payload)

        event_queue.task_done()


def _execute_handler(handler, event_type, payload):
    """Execute a handler with retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with _app.app_context():
                handler(payload)
                _update_job_status(event_type, payload, 'completed')
            return
        except Exception as e:
            logger.error(f"Handler failed (attempt {attempt+1}/{max_retries}): {event_type} - {e}")
            if attempt == max_retries - 1:
                _update_job_status(event_type, payload, 'failed', str(e))


def _default_dispatch(event_type, payload):
    """Default event dispatch when no specific handler is registered."""
    try:
        with _app.app_context():
            if event_type == 'resume_uploaded':
                from core.resume_processor import process_resume
                process_resume(payload)

            elif event_type == 'referral_requested':
                from core.ranking_engine import rank_candidates
                rank_candidates(payload)

            elif event_type == 'profile_updated':
                from core.recommendation_engine import recompute_recommendations
                recompute_recommendations(payload)

            elif event_type == 'post_created':
                # Could trigger notifications or feed updates
                pass

            elif event_type == 'message_sent':
                from core.notifications import notify_new_message
                notify_new_message(payload)

            _update_job_status(event_type, payload, 'completed')
    except Exception as e:
        logger.error(f"Default dispatch failed: {event_type} - {e}")
        _update_job_status(event_type, payload, 'failed', str(e))


def _update_job_status(event_type, payload, status, error=''):
    """Update the persistent job status in the database."""
    try:
        from app.extensions import db
        from app.models import JobQueue

        job = JobQueue.query.filter_by(
            event_type=event_type,
            status='pending'
        ).order_by(JobQueue.created_at.desc()).first()

        if job:
            job.status = status
            if error:
                job.error_message = error
                job.retries += 1
            db.session.commit()
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")

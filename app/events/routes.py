from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.events import bp
from app.auth.decorators import role_required
from app.extensions import db
from app.models import Event, EventRSVP, Department
from datetime import datetime, timezone


@bp.route('/')
@login_required
def index():
    return render_template('events/list.html')


@bp.route('/api/list')
@login_required
def list_events():
    filter_type = request.args.get('type', '')
    scope = request.args.get('scope', 'upcoming')  # upcoming, past, all
    page = request.args.get('page', 1, type=int)

    query = Event.query.filter_by(is_active=True)

    if filter_type:
        query = query.filter_by(event_type=filter_type)

    now = datetime.now(timezone.utc)
    if scope == 'upcoming':
        query = query.filter((Event.start_time >= now) | (Event.start_time.is_(None)))
        query = query.order_by(Event.start_time.asc())
    elif scope == 'past':
        query = query.filter(Event.start_time < now)
        query = query.order_by(Event.start_time.desc())
    else:
        query = query.order_by(Event.created_at.desc())

    events = query.paginate(page=page, per_page=20)

    return jsonify({
        'events': [{
            'id': e.id,
            'title': e.title,
            'description': e.description[:300],
            'event_type': e.event_type,
            'start_time': e.start_time.isoformat() if e.start_time else None,
            'end_time': e.end_time.isoformat() if e.end_time else None,
            'location': e.location,
            'is_virtual': e.is_virtual,
            'meeting_link': e.meeting_link if e.is_virtual else '',
            'creator': e.creator.username,
            'creator_name': e.creator.profile.full_name if e.creator.profile else e.creator.username,
            'department': e.department.name if e.department else 'All',
            'rsvp_count': e.rsvp_count,
            'max_attendees': e.max_attendees,
            'my_rsvp': _get_user_rsvp(e.id, current_user.id),
            'created_at': e.created_at.isoformat()
        } for e in events.items],
        'total': events.total,
        'pages': events.pages,
        'page': page
    })


@bp.route('/api/upcoming-widget')
@login_required
def upcoming_widget():
    """Get next 5 upcoming events for dashboard widget."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    events = Event.query.filter(
        Event.is_active == True,
        Event.start_time >= now
    ).order_by(Event.start_time.asc()).limit(5).all()

    return jsonify([{
        'id': e.id,
        'title': e.title,
        'event_type': e.event_type,
        'start_time': e.start_time.isoformat() if e.start_time else None,
        'location': e.location,
        'is_virtual': e.is_virtual,
        'rsvp_count': e.rsvp_count
    } for e in events])


@bp.route('/api/create', methods=['POST'])
@login_required
@role_required('admin', 'faculty')
def create_event():
    data = request.get_json()
    if not data or not data.get('title', '').strip():
        return jsonify({'error': 'Title is required'}), 400

    event = Event(
        title=data['title'].strip(),
        description=data.get('description', '').strip(),
        event_type=data.get('event_type', 'event'),
        created_by=current_user.id,
        department_id=data.get('department_id') or None,
        location=data.get('location', '').strip(),
        is_virtual=data.get('is_virtual', False),
        meeting_link=data.get('meeting_link', '').strip(),
        max_attendees=data.get('max_attendees') or None,
        contact_email=data.get('contact_email', '').strip(),
    )

    # Parse datetime strings
    if data.get('start_time'):
        try:
            event.start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            pass
    if data.get('end_time'):
        try:
            event.end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            pass
    if data.get('registration_deadline'):
        try:
            event.registration_deadline = datetime.fromisoformat(data['registration_deadline'].replace('Z', '+00:00'))
        except (ValueError, TypeError):
            pass

    db.session.add(event)
    db.session.commit()

    return jsonify({'id': event.id, 'message': 'Event created successfully'}), 201


@bp.route('/api/<int:event_id>', methods=['PUT'])
@login_required
@role_required('admin', 'faculty')
def update_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404

    data = request.get_json()
    if data.get('title'):
        event.title = data['title'].strip()
    if 'description' in data:
        event.description = data['description'].strip()
    if 'event_type' in data:
        event.event_type = data['event_type']
    if 'location' in data:
        event.location = data['location'].strip()
    if 'is_virtual' in data:
        event.is_virtual = data['is_virtual']
    if 'meeting_link' in data:
        event.meeting_link = data['meeting_link'].strip()
    if 'is_active' in data:
        event.is_active = data['is_active']

    db.session.commit()
    return jsonify({'message': 'Event updated'})


@bp.route('/api/<int:event_id>', methods=['DELETE'])
@login_required
@role_required('admin', 'faculty')
def delete_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    event.is_active = False
    db.session.commit()
    return jsonify({'message': 'Event cancelled'})


@bp.route('/api/<int:event_id>/rsvp', methods=['POST'])
@login_required
def rsvp_event(event_id):
    event = db.session.get(Event, event_id)
    if not event or not event.is_active:
        return jsonify({'error': 'Event not found'}), 404

    data = request.get_json()
    status = data.get('status', 'attending')  # attending, maybe, declined

    existing = EventRSVP.query.filter_by(event_id=event_id, user_id=current_user.id).first()
    if existing:
        if status == 'cancel':
            db.session.delete(existing)
            db.session.commit()
            return jsonify({'message': 'RSVP cancelled', 'rsvp_count': event.rsvp_count})
        existing.status = status
    else:
        rsvp = EventRSVP(event_id=event_id, user_id=current_user.id, status=status)
        db.session.add(rsvp)

    db.session.commit()
    return jsonify({'status': status, 'rsvp_count': event.rsvp_count})


def _get_user_rsvp(event_id, user_id):
    rsvp = EventRSVP.query.filter_by(event_id=event_id, user_id=user_id).first()
    return rsvp.status if rsvp else None

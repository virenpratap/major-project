from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.mentorship import bp
from app.extensions import db
from app.models import User, Profile, MentorshipRequest, Department, Tag, UserTag
from datetime import datetime, timezone


@bp.route('/')
@login_required
def index():
    if current_user.role == 'alumni':
        return render_template('mentorship/dashboard.html')
    return redirect(url_for('mentorship.find_mentors'))


@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('mentorship/dashboard.html')


@bp.route('/find')
@login_required
def find_mentors():
    """Search for alumni available for mentorship."""
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    return render_template('mentorship/find.html', departments=departments)


@bp.route('/api/search')
@login_required
def api_search_mentors():
    industry = request.args.get('industry', '')
    dept_id = request.args.get('department_id', type=int)
    skill = request.args.get('skill', '')
    page = request.args.get('page', 1, type=int)

    query = User.query.join(Profile).filter(
        User.role == 'alumni',
        Profile.is_mentor_available == True,
        User.is_active == True
    )

    if industry:
        query = query.filter(Profile.industry.ilike(f'%{industry}%'))
    
    if dept_id:
        query = query.filter(Profile.department_id == dept_id)

    if skill:
        query = query.join(UserTag).join(Tag).filter(Tag.name.ilike(f'%{skill}%'))

    mentors = query.order_by(User.created_at.desc()).paginate(page=page, per_page=12)

    return jsonify({
        'mentors': [{
            'id': m.id,
            'name': m.profile.full_name,
            'title': m.profile.title,
            'company': m.profile.company,
            'industry': m.profile.industry,
            'location': m.profile.location,
            'department': m.profile.department.name if m.profile.department else '',
            'avatar': url_for('main.get_avatar', user_id=m.id),
            'skills': [t.name for t in db.session.query(Tag).join(UserTag).filter(UserTag.user_id == m.id).limit(3).all()]
        } for m in mentors.items],
        'total': mentors.total,
        'pages': mentors.pages,
        'page': page
    })


@bp.route('/api/request', methods=['POST'])
@login_required
def request_mentorship():
    data = request.get_json()
    mentor_id = data.get('mentor_id')
    message = data.get('message', '').strip()

    if not mentor_id or not message:
        return jsonify({'error': 'Mentor and message are required'}), 400

    mentor = db.session.get(User, mentor_id)
    if not mentor or mentor.role != 'alumni' or not mentor.profile.is_mentor_available:
        return jsonify({'error': 'Invalid mentor selected'}), 400

    # Check if a pending request already exists
    existing = MentorshipRequest.query.filter_by(
        student_id=current_user.id,
        mentor_id=mentor_id,
        status='pending'
    ).first()
    
    if existing:
        return jsonify({'error': 'You already have a pending request for this mentor'}), 400

    req = MentorshipRequest(
        student_id=current_user.id,
        mentor_id=mentor_id,
        message=message
    )
    db.session.add(req)
    db.session.commit()

    # Notify mentor
    from core.notifications import send_notification
    send_notification(mentor_id, 'mentorship_requested', {
        'student_id': current_user.id,
        'student_name': current_user.profile.full_name,
        'message': f'{current_user.profile.full_name} has requested mentorship from you.'
    })

    return jsonify({'message': 'Mentorship request sent successfully'})


@bp.route('/api/my-requests')
@login_required
def get_my_requests():
    """Get outgoing requests (for students) or incoming requests (for mentors)."""
    if current_user.role == 'alumni':
        # Incoming requests
        reqs = MentorshipRequest.query.filter_by(mentor_id=current_user.id).order_by(MentorshipRequest.created_at.desc()).all()
        return jsonify([{
            'id': r.id,
            'student_id': r.student_id,
            'student_name': r.student.profile.full_name,
            'student_title': r.student.profile.title or 'Student',
            'student_dept': r.student.profile.department.name if r.student.profile.department else '',
            'student_avatar': url_for('main.get_avatar', user_id=r.student_id),
            'message': r.message,
            'status': r.status,
            'created_at': r.created_at.isoformat()
        } for r in reqs])
    else:
        # Outgoing requests
        reqs = MentorshipRequest.query.filter_by(student_id=current_user.id).order_by(MentorshipRequest.created_at.desc()).all()
        return jsonify([{
            'id': r.id,
            'mentor_id': r.mentor_id,
            'mentor_name': r.mentor.profile.full_name,
            'mentor_title': r.mentor.profile.title or 'Alumni',
            'mentor_avatar': url_for('main.get_avatar', user_id=r.mentor_id),
            'status': r.status,
            'created_at': r.created_at.isoformat()
        } for r in reqs])


@bp.route('/api/request/<int:request_id>/status', methods=['POST'])
@login_required
def update_request_status(request_id):
    req = db.session.get(MentorshipRequest, request_id)
    if not req or req.mentor_id != current_user.id:
        return jsonify({'error': 'Request not found'}), 404

    data = request.get_json()
    status = data.get('status')
    if status not in ['accepted', 'rejected']:
        return jsonify({'error': 'Invalid status'}), 400

    req.status = status
    if status == 'rejected':
        req.rejection_reason = data.get('reason', '')

    db.session.commit()

    # Notify student
    from core.notifications import send_notification
    msg = f'Your mentorship request to {current_user.profile.full_name} has been {status}.'
    send_notification(req.student_id, 'mentorship_status_update', {
        'mentor_id': current_user.id,
        'status': status,
        'message': msg
    })

    # If accepted, automatically create a connection
    if status == 'accepted':
        from app.models import Connection
        existing_conn = Connection.query.filter(
            ((Connection.user_id == req.student_id) & (Connection.target_id == req.mentor_id)) |
            ((Connection.user_id == req.mentor_id) & (Connection.target_id == req.student_id))
        ).first()
        
        if not existing_conn:
            conn = Connection(user_id=req.student_id, target_id=req.mentor_id, status='accepted')
            db.session.add(conn)
            db.session.commit()

    return jsonify({'message': f'Request {status}'})

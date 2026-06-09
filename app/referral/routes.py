from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.referral import bp
from app.extensions import db
from app.models import Referral, Job, User, Resume
from app.auth.decorators import role_required
from core.event_bus import publish
from core.ai_client import complete
import json


@bp.route('/')
@login_required
def index():
    if current_user.role == 'alumni':
        return render_template('referral/dashboard.html')
    return render_template('referral/apply.html')


@bp.route('/dashboard')
@login_required
@role_required('alumni', 'admin')
def dashboard():
    return render_template('referral/dashboard.html')


@bp.route('/api/jobs', methods=['GET'])
@login_required
def list_jobs():
    jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).all()
    return jsonify([{
        'id': j.id,
        'title': j.title,
        'company': j.company,
        'location': j.location,
        'type': j.job_type,
        'skills': j.skills_list,
        'posted_by': j.poster.username,
        'created_at': j.created_at.isoformat()
    } for j in jobs])


@bp.route('/api/jobs', methods=['POST'])
@login_required
@role_required('alumni', 'admin')
def create_job():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid data'}), 400

    job = Job(
        posted_by=current_user.id,
        title=data.get('title', ''),
        company=data.get('company', ''),
        description=data.get('description', ''),
        location=data.get('location', ''),
        job_type=data.get('type', 'full-time'),
        skills_required=json.dumps(data.get('skills', []))
    )
    db.session.add(job)
    db.session.commit()

    return jsonify({'id': job.id, 'message': 'Job posted successfully'}), 201


@bp.route('/api/apply', methods=['POST'])
@login_required
@role_required('student')
def apply_referral():
    data = request.get_json()
    job_id = data.get('job_id')

    if not job_id:
        return jsonify({'error': 'Job ID required'}), 400

    job = db.session.get(Job, job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # Check for existing application
    existing = Referral.query.filter_by(job_id=job_id, student_id=current_user.id).first()
    if existing:
        return jsonify({'error': 'Already applied', 'status': existing.status}), 400

    # Check if student has a resume
    resume = Resume.query.filter_by(user_id=current_user.id, status='completed').first()
    if not resume:
        return jsonify({'error': 'Please upload and analyze your resume first'}), 400

    referral = Referral(
        job_id=job_id,
        student_id=current_user.id,
        alumni_id=job.posted_by,
        status='applied'
    )
    db.session.add(referral)
    db.session.commit()

    # Trigger ranking
    publish('referral_requested', {'job_id': job_id})

    return jsonify({
        'id': referral.id,
        'status': 'applied',
        'message': 'Application submitted! Ranking in progress.'
    }), 201


@bp.route('/api/candidates/<int:job_id>')
@login_required
@role_required('alumni', 'admin')
def get_candidates(job_id):
    referrals = Referral.query.filter_by(job_id=job_id).order_by(Referral.rank.asc()).all()

    candidates = []
    for r in referrals:
        student = db.session.get(User, r.student_id)
        profile = student.profile if student else None
        resume = Resume.query.filter_by(user_id=r.student_id, status='completed').first()

        candidates.append({
            'referral_id': r.id,
            'student_id': r.student_id,
            'name': profile.full_name if profile else (student.username if student else 'Unknown'),
            'title': profile.title if profile else '',
            'rank': r.rank,
            'score': r.rank_score,
            'explanation': json.loads(r.rank_explanation) if r.rank_explanation else {},
            'status': r.status,
            'resume_score': resume.score if resume else 0,
            'created_at': r.created_at.isoformat()
        })

    return jsonify(candidates)


@bp.route('/api/select/<int:referral_id>', methods=['POST'])
@login_required
@role_required('alumni', 'admin')
def select_candidate(referral_id):
    referral = db.session.get(Referral, referral_id)
    if not referral:
        return jsonify({'error': 'Referral not found'}), 404

    # Update status
    referral.status = 'selected'
    db.session.commit()

    # Generate referral message via AI
    student = db.session.get(User, referral.student_id)
    job = db.session.get(Job, referral.job_id)

    message = complete(
        f"""Generate a professional referral message for:
Candidate: {student.profile.full_name if student and student.profile else 'the candidate'}
Position: {job.title if job else 'the position'} at {job.company if job else 'the company'}
Score: {referral.rank_score}/100

Write a concise, professional referral letter (3-4 paragraphs).""",
        system_prompt="You are a professional career mentor writing referral letters."
    )

    referral.referral_message = message
    db.session.commit()

    # Adaptive weight update
    from core.ranking_engine import update_weights_from_feedback
    update_weights_from_feedback(referral.job_id, referral_id)

    # Notify student
    from core.notifications import notify_referral_update
    notify_referral_update(referral.student_id, referral_id, 'selected')

    return jsonify({
        'status': 'selected',
        'referral_message': message,
        'message': 'Candidate selected and referral generated!'
    })


@bp.route('/api/referral/<int:referral_id>/status', methods=['POST'])
@login_required
@role_required('alumni', 'admin')
def update_status(referral_id):
    referral = db.session.get(Referral, referral_id)
    if not referral or (referral.alumni_id != current_user.id and current_user.role != 'admin'):
        return jsonify({'error': 'Referral not found or access denied'}), 404

    data = request.get_json()
    new_status = data.get('status')
    allowed_statuses = ['applied', 'selected', 'referred', 'interviewing', 'hired', 'rejected']
    
    if new_status not in allowed_statuses:
        return jsonify({'error': 'Invalid status'}), 400

    referral.status = new_status
    db.session.commit()

    # Notify student
    from core.notifications import send_notification
    msg = f"Your application for {referral.job.title} at {referral.job.company} status updated to: {new_status.replace('_', ' ').capitalize()}"
    send_notification(referral.student_id, 'referral_status_update', {
        'referral_id': referral.id,
        'status': new_status,
        'message': msg
    })

    return jsonify({'status': new_status, 'message': 'Status updated successfully'})


@bp.route('/api/my-jobs')
@login_required
@role_required('alumni', 'admin')
def my_jobs():
    jobs = Job.query.filter_by(posted_by=current_user.id).order_by(Job.created_at.desc()).all()
    return jsonify([{
        'id': j.id,
        'title': j.title,
        'company': j.company,
        'applications_count': Referral.query.filter_by(job_id=j.id).count(),
        'created_at': j.created_at.isoformat()
    } for j in jobs])


@bp.route('/api/jobs/<int:job_id>/applicants')
@login_required
@role_required('alumni', 'admin')
def get_applicants(job_id):
    referrals = Referral.query.filter_by(job_id=job_id).order_by(Referral.rank.asc()).all()
    candidates = []
    for r in referrals:
        student = db.session.get(User, r.student_id)
        candidates.append({
            'id': r.id,
            'student_id': r.student_id,
            'student_name': student.profile.full_name if student and student.profile else student.username,
            'score': r.rank_score,
            'status': r.status,
            'created_at': r.created_at.isoformat()
        })
    return jsonify(candidates)


@bp.route('/api/referral/<int:referral_id>')
@login_required
def get_referral_detail(referral_id):
    r = db.session.get(Referral, referral_id)
    if not r or (r.student_id != current_user.id and r.alumni_id != current_user.id and current_user.role != 'admin'):
        return jsonify({'error': 'Referral not found or access denied'}), 404

    return jsonify({
        'id': r.id,
        'job': {
            'title': r.job.title,
            'company': r.job.company,
            'location': r.job.location,
            'description': r.job.description
        },
        'status': r.status,
        'rank': r.rank,
        'score': r.rank_score,
        'explanation': json.loads(r.rank_explanation) if r.rank_explanation else {},
        'referral_message': r.referral_message,
        'created_at': r.created_at.isoformat(),
        'updated_at': r.updated_at.isoformat()
    })


@bp.route('/api/my-applications')
@login_required
def my_applications():
    referrals = Referral.query.filter_by(student_id=current_user.id).order_by(Referral.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'job_id': r.job_id,
        'job_title': r.job.title if r.job else '',
        'company': r.job.company if r.job else '',
        'status': r.status,
        'rank': r.rank,
        'score': r.rank_score,
        'created_at': r.created_at.isoformat()
    } for r in referrals])

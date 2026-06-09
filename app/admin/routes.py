from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.admin import bp
from app.auth.decorators import admin_required
from app.extensions import db
from app.models import (User, Profile, Post, Comment, Resume, Referral, Job, Department, Batch,
                         Notification, ModelWeight, JobQueue, AuditLog, LLMLog, Event)
from datetime import datetime, timezone, timedelta
import json


@bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'pending_approvals': User.query.filter_by(is_approved=False, is_active=True).count(),
        'students': User.query.filter_by(role='student').count(),
        'alumni': User.query.filter_by(role='alumni').count(),
        'faculty': User.query.filter_by(role='faculty').count(),
        'total_posts': Post.query.count(),
        'total_resumes': Resume.query.count(),
        'total_referrals': Referral.query.count(),
        'total_events': Event.query.filter_by(is_active=True).count(),
        'departments': Department.query.filter_by(is_active=True).count(),
        'pending_jobs': JobQueue.query.filter_by(status='pending').count(),
        'failed_jobs': JobQueue.query.filter_by(status='failed').count(),
    }
    return render_template('admin/dashboard.html', stats=stats)


@bp.route('/users')
@login_required
@admin_required
def users():
    return render_template('admin/users.html')


@bp.route('/api/users')
@login_required
@admin_required
def api_users():
    role = request.args.get('role')
    status = request.args.get('status')
    approval = request.args.get('approval')
    page = request.args.get('page', 1, type=int)

    query = User.query
    if role:
        query = query.filter_by(role=role)
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    if approval == 'pending':
        query = query.filter_by(is_approved=False)
    elif approval == 'approved':
        query = query.filter_by(is_approved=True)

    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20)

    return jsonify({
        'users': [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'role': u.role,
            'is_active': u.is_active,
            'is_approved': u.is_approved,
            'name': u.profile.full_name if u.profile else '',
            'department': u.profile.department.code if u.profile and u.profile.department else '',
            'phone': u.profile.phone if u.profile else '',
            'enrollment_number': u.profile.enrollment_number if u.profile else '',
            'graduation_year': u.profile.graduation_year if u.profile else None,
            'last_login': u.last_login_at.isoformat() if u.last_login_at else None,
            'login_count': u.login_count or 0,
            'created_at': u.created_at.isoformat()
        } for u in users.items],
        'total': users.total,
        'pages': users.pages,
        'page': page
    })


# ─── Pending Approvals ───

@bp.route('/api/pending-users')
@login_required
@admin_required
def api_pending_users():
    users = User.query.filter_by(is_approved=False, is_active=True).order_by(User.created_at.desc()).all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'role': u.role,
        'name': u.profile.full_name if u.profile else '',
        'department': u.profile.department.name if u.profile and u.profile.department else '',
        'enrollment_number': u.profile.enrollment_number if u.profile else '',
        'phone': u.profile.phone if u.profile else '',
        'created_at': u.created_at.isoformat()
    } for u in users])


@bp.route('/api/users/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.is_approved = True
    user.approved_by = current_user.id
    user.approved_at = datetime.now(timezone.utc)
    _audit('approve_user', f'Approved {user.username} ({user.role})')
    db.session.commit()

    # Notify user
    from core.notifications import send_notification
    send_notification(user_id, 'registration_approved', {
        'message': 'Your registration has been approved! Welcome to AlumniNet.'
    })

    return jsonify({'message': f'{user.username} approved', 'is_approved': True})


@bp.route('/api/users/<int:user_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_user(user_id):
    data = request.get_json()
    reason = data.get('reason', 'Registration rejected by administrator.') if data else ''

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.is_active = False
    user.rejection_reason = reason
    _audit('reject_user', f'Rejected {user.username}: {reason}')
    db.session.commit()

    return jsonify({'message': f'{user.username} rejected'})


@bp.route('/api/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.is_active = not user.is_active
    _audit('toggle_user_active', f'User {user.username}: active={user.is_active}')
    db.session.commit()

    return jsonify({'is_active': user.is_active})


@bp.route('/api/users/<int:user_id>/change-role', methods=['POST'])
@login_required
@admin_required
def change_user_role(user_id):
    data = request.get_json()
    new_role = data.get('role')
    if new_role not in ('student', 'alumni', 'faculty', 'admin'):
        return jsonify({'error': 'Invalid role'}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    old_role = user.role
    user.role = new_role
    _audit('change_role', f'User {user.username}: {old_role} -> {new_role}')
    db.session.commit()

    return jsonify({'role': new_role})


# ─── Batch / Department Tree Management ───

@bp.route('/batches')
@login_required
@admin_required
def batches():
    return render_template('admin/batches.html')


@bp.route('/api/tree')
@login_required
@admin_required
def api_tree():
    departments = Department.query.order_by(Department.name).all()
    tree = []
    for dept in departments:
        dept_batches = Batch.query.filter_by(department_id=dept.id).order_by(Batch.year.desc()).all()
        tree.append({
            'id': dept.id,
            'name': dept.name,
            'code': dept.code,
            'head_name': dept.head_name,
            'head_email': dept.head_email,
            'is_active': dept.is_active,
            'batches': [{
                'id': b.id,
                'year': b.year,
                'section': b.section,
                'total_strength': b.total_strength,
                'is_active': b.is_active,
                'is_passed_out': b.is_passed_out,
                'passed_out_at': b.passed_out_at.isoformat() if b.passed_out_at else None,
                'student_count': Profile.query.filter_by(batch_id=b.id).count()
            } for b in dept_batches]
        })
    return jsonify(tree)


@bp.route('/api/departments', methods=['POST'])
@login_required
@admin_required
def create_department():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('code'):
        return jsonify({'error': 'Name and code are required'}), 400

    if Department.query.filter_by(code=data['code'].upper()).first():
        return jsonify({'error': 'Department code already exists'}), 400

    dept = Department(
        name=data['name'].strip(),
        code=data['code'].strip().upper(),
        description=data.get('description', '').strip(),
        head_name=data.get('head_name', '').strip(),
        head_email=data.get('head_email', '').strip()
    )
    db.session.add(dept)
    db.session.commit()
    _audit('create_department', f'{dept.code} - {dept.name}')
    return jsonify({'id': dept.id, 'message': f'Department {dept.code} created'}), 201


@bp.route('/api/batches', methods=['POST'])
@login_required
@admin_required
def create_batch():
    data = request.get_json()
    if not data or not data.get('year') or not data.get('department_id'):
        return jsonify({'error': 'Year and department are required'}), 400

    batch = Batch(
        year=int(data['year']),
        department_id=int(data['department_id']),
        section=data.get('section', '').strip(),
        total_strength=int(data.get('total_strength', 0))
    )
    db.session.add(batch)
    db.session.commit()
    _audit('create_batch', f'Batch {batch.year} for dept {batch.department_id}')
    return jsonify({'id': batch.id, 'message': 'Batch created'}), 201


@bp.route('/api/batches/<int:batch_id>/passout', methods=['POST'])
@login_required
@admin_required
def passout_batch(batch_id):
    """Mark entire batch as passed out: change all students to alumni."""
    batch = db.session.get(Batch, batch_id)
    if not batch:
        return jsonify({'error': 'Batch not found'}), 404

    batch.is_passed_out = True
    batch.passed_out_at = datetime.now(timezone.utc)

    # Bulk update all students in this batch to alumni
    profiles = Profile.query.filter_by(batch_id=batch_id).all()
    count = 0
    for profile in profiles:
        user = profile.user
        if user and user.role == 'student':
            user.role = 'alumni'
            count += 1

    db.session.commit()
    _audit('batch_passout', f'Batch {batch.year} dept={batch.department_id}: {count} students → alumni')
    return jsonify({'message': f'Batch passed out. {count} students converted to alumni.'})


@bp.route('/api/batches/<int:batch_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_batch_active(batch_id):
    batch = db.session.get(Batch, batch_id)
    if not batch:
        return jsonify({'error': 'Batch not found'}), 404
    batch.is_active = not batch.is_active
    db.session.commit()
    _audit('toggle_batch', f'Batch {batch.year}: active={batch.is_active}')
    return jsonify({'is_active': batch.is_active})


@bp.route('/api/departments/<int:dept_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_department_active(dept_id):
    dept = db.session.get(Department, dept_id)
    if not dept:
        return jsonify({'error': 'Department not found'}), 404
    dept.is_active = not dept.is_active
    # Cascade to batches
    for batch in dept.batches:
        batch.is_active = dept.is_active
    db.session.commit()
    _audit('toggle_department', f'{dept.code}: active={dept.is_active}')
    return jsonify({'is_active': dept.is_active})


# ─── Analytics ───

@bp.route('/api/analytics/stats')
@login_required
@admin_required
def api_analytics_stats():
    """Get statistics for dashboard charts."""
    from sqlalchemy import func, extract
    
    # 1. Role Distribution
    role_dist = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
    role_data = {r: c for r, c in role_dist}

    # 2. Departmental Breakdown
    dept_dist = db.session.query(Department.code, func.count(Profile.id))\
        .join(Profile, Profile.department_id == Department.id)\
        .group_by(Department.code).all()
    dept_labels = [d[0] for d in dept_dist]
    dept_counts = [d[1] for d in dept_dist]

    # 3. Monthly Registration Trends (Last 6 months)
    six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
    reg_trends = db.session.query(
        extract('month', User.created_at).label('month'),
        func.count(User.id)
    ).filter(User.created_at >= six_months_ago)\
     .group_by('month')\
     .order_by('month').all()
    
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    trend_labels = [month_names[int(r[0])-1] for r in reg_trends]
    trend_counts = [r[1] for r in reg_trends]

    # 4. Job/Referral Success
    referral_stats = db.session.query(Referral.status, func.count(Referral.id))\
        .group_by(Referral.status).all()
    referral_data = {s: c for s, c in referral_stats}

    return jsonify({
        'role_dist': role_data,
        'dept_breakdown': {
            'labels': dept_labels,
            'counts': dept_counts
        },
        'reg_trends': {
            'labels': trend_labels,
            'counts': trend_counts
        },
        'referral_stats': referral_data
    })


# ─── Existing Admin Routes ───

@bp.route('/resumes')
@login_required
@admin_required
def resumes():
    return render_template('admin/resumes.html')


@bp.route('/api/resumes')
@login_required
@admin_required
def api_resumes():
    page = request.args.get('page', 1, type=int)
    resumes = Resume.query.order_by(Resume.created_at.desc()).paginate(page=page, per_page=20)

    return jsonify({
        'resumes': [{
            'id': r.id,
            'user': r.owner.username,
            'filename': r.filename,
            'score': r.score,
            'status': r.status,
            'is_validated': r.is_validated,
            'created_at': r.created_at.isoformat()
        } for r in resumes.items],
        'total': resumes.total,
        'pages': resumes.pages
    })


@bp.route('/referrals')
@login_required
@admin_required
def referrals():
    return render_template('admin/referrals.html')


@bp.route('/moderation')
@login_required
@admin_required
def moderation():
    return render_template('admin/moderation.html')


@bp.route('/api/posts/delete/<int:post_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    _audit('delete_post', f'Post {post_id} by {post.author.username}')
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Post deleted'})


@bp.route('/llm-logs')
@login_required
@admin_required
def llm_logs():
    return render_template('admin/llm_logs.html')


@bp.route('/api/llm-logs')
@login_required
@admin_required
def api_llm_logs():
    page = request.args.get('page', 1, type=int)
    logs = LLMLog.query.order_by(LLMLog.created_at.desc()).paginate(page=page, per_page=20)

    return jsonify({
        'logs': [{
            'id': l.id,
            'prompt': l.prompt[:200],
            'response': l.response[:200],
            'tokens': l.tokens_used,
            'duration_ms': l.duration_ms,
            'model': l.model,
            'created_at': l.created_at.isoformat()
        } for l in logs.items],
        'total': logs.total
    })


@bp.route('/jobs')
@login_required
@admin_required
def jobs():
    return render_template('admin/jobs.html')


@bp.route('/api/jobs-queue')
@login_required
@admin_required
def api_jobs_queue():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status')

    query = JobQueue.query
    if status:
        query = query.filter_by(status=status)

    jobs = query.order_by(JobQueue.created_at.desc()).paginate(page=page, per_page=20)

    return jsonify({
        'jobs': [{
            'id': j.id,
            'event_type': j.event_type,
            'status': j.status,
            'retries': j.retries,
            'error': j.error_message[:200] if j.error_message else '',
            'created_at': j.created_at.isoformat()
        } for j in jobs.items],
        'total': jobs.total
    })


@bp.route('/audit')
@login_required
@admin_required
def audit():
    return render_template('admin/audit.html')


@bp.route('/api/audit-logs')
@login_required
@admin_required
def api_audit_logs():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=30)

    return jsonify({
        'logs': [{
            'id': l.id,
            'actor': l.actor.username if l.actor else 'System',
            'action': l.action,
            'target': l.target,
            'details': l.details,
            'timestamp': l.timestamp.isoformat()
        } for l in logs.items],
        'total': logs.total
    })


@bp.route('/api/weights', methods=['GET'])
@login_required
@admin_required
def get_weights():
    weights = ModelWeight.query.all()
    return jsonify([{
        'id': w.id,
        'context': w.context,
        'weights': w.weights,
        'version': w.version
    } for w in weights])


@bp.route('/api/weights/<int:weight_id>', methods=['PUT'])
@login_required
@admin_required
def update_weights(weight_id):
    data = request.get_json()
    weight = db.session.get(ModelWeight, weight_id)
    if not weight:
        return jsonify({'error': 'Weight config not found'}), 404

    weight.weights = data.get('weights', weight.weights)
    weight.version += 1
    _audit('update_weights', f'{weight.context} v{weight.version}')
    db.session.commit()

    return jsonify({'message': 'Weights updated', 'version': weight.version})


@bp.route('/api/recompute-rankings', methods=['POST'])
@login_required
@admin_required
def recompute_rankings():
    """Recompute rankings for all active jobs."""
    from core.event_bus import publish

    active_jobs = Job.query.filter_by(is_active=True).all()
    for job in active_jobs:
        referral_count = Referral.query.filter_by(job_id=job.id).count()
        if referral_count > 0:
            publish('referral_requested', {'job_id': job.id})

    _audit('recompute_rankings', f'{len(active_jobs)} jobs queued')
    return jsonify({'message': f'Ranking recomputation queued for {len(active_jobs)} jobs'})


def _audit(action, details=''):
    """Create an audit log entry."""
    log = AuditLog(
        actor_id=current_user.id,
        action=action,
        target=details,
        ip_address=request.remote_addr or ''
    )
    db.session.add(log)

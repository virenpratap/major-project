from flask import render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from app.resume import bp
from app.extensions import db
from app.models import Resume
from core.encryption import get_storage_path, encrypt_and_save
from core.event_bus import publish
import os
import uuid


@bp.route('/')
@login_required
def index():
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).all()
    return render_template('resume/upload.html', resumes=resumes)


@bp.route('/analysis/<int:resume_id>')
@login_required
def analysis(resume_id):
    resume = db.session.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        return render_template('resume/analysis.html', resume=None, error='Resume not found')
    return render_template('resume/analysis.html', resume=resume)


@bp.route('/api/upload', methods=['POST'])
@login_required
def upload_resume():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    # Validate file type
    allowed = {'.pdf', '.docx', '.txt'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({'error': f'File type {ext} not supported. Use: {", ".join(allowed)}'}), 400

    # Read file data
    file_data = file.read()
    if len(file_data) > current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024):
        return jsonify({'error': 'File too large (max 16MB)'}), 400

    # Encrypt and save
    file_path = get_storage_path(current_user.id)
    encrypt_and_save(file_data, file_path)

    # Create resume record
    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        status='pending'
    )
    db.session.add(resume)
    db.session.commit()

    # Publish event for background processing
    publish('resume_uploaded', {
        'resume_id': resume.id,
        'user_id': current_user.id
    })

    return jsonify({
        'id': resume.id,
        'filename': resume.filename,
        'status': 'pending',
        'message': 'Resume uploaded! Analysis will begin shortly.'
    }), 201


@bp.route('/api/<int:resume_id>/analysis')
@login_required
def get_analysis(resume_id):
    resume = db.session.get(Resume, resume_id)
    if not resume:
        return jsonify({'error': 'Resume not found'}), 404

    # Check access
    if resume.user_id != current_user.id and current_user.role not in ('admin', 'faculty'):
        return jsonify({'error': 'Access denied'}), 403

    return jsonify({
        'id': resume.id,
        'filename': resume.filename,
        'status': resume.status,
        'score': resume.score,
        'analysis': resume.analysis,
        'created_at': resume.created_at.isoformat()
    })


@bp.route('/api/<int:resume_id>/status')
@login_required
def get_status(resume_id):
    resume = db.session.get(Resume, resume_id)
    if not resume or resume.user_id != current_user.id:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'status': resume.status, 'score': resume.score})

from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.main import bp
from app.extensions import db
from app.models import User, Profile, Tag, UserTag, Post, Connection, Resume, Notification, Referral, Job, Event
from core.encryption import encrypt_and_save, decrypt_and_read, get_avatar_path
from core.notifications import get_notifications
from datetime import datetime, timezone
import io
from PIL import Image


@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')


@bp.route('/dashboard')
@login_required
def dashboard():
    # Role-specific dashboard stats
    notifications = get_notifications(current_user.id, limit=5)
    
    stats = {}
    if current_user.role == 'student':
        stats = {
            'resume_score': Resume.query.filter_by(user_id=current_user.id).order_by(Resume.created_at.desc()).first().score if Resume.query.filter_by(user_id=current_user.id).first() else 0,
            'connections': Connection.query.filter(
                ((Connection.user_id == current_user.id) | (Connection.target_id == current_user.id)) &
                (Connection.status == 'accepted')
            ).count(),
            'referrals_applied': Referral.query.filter_by(student_id=current_user.id).count(),
            'my_posts': Post.query.filter_by(author_id=current_user.id).count(),
        }
    elif current_user.role == 'alumni':
        stats = {
            'referrals_given': Referral.query.filter_by(alumni_id=current_user.id).count(),
            'connections': Connection.query.filter(
                ((Connection.user_id == current_user.id) | (Connection.target_id == current_user.id)) &
                (Connection.status == 'accepted')
            ).count(),
            'active_jobs': Job.query.filter_by(posted_by=current_user.id, is_active=True).count(),
            'unread_messages': 0, # Placeholder
        }
    elif current_user.role == 'admin':
        stats = {
            'total_users': User.query.count(),
            'pending_approvals': User.query.filter_by(is_approved=False).count(),
            'failed_jobs': 0, # Placeholder
            'system_health': 'Good'
        }

    return render_template('main/dashboard.html', stats=stats, notifications=notifications)


@bp.route('/profile')
@login_required
def profile():
    return redirect(url_for('main.view_profile', user_id=current_user.id))


@bp.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('main.dashboard'))

    user_tags = db.session.query(Tag).join(UserTag).filter(UserTag.user_id == user_id).all()
    
    connection = Connection.query.filter(
        ((Connection.user_id == current_user.id) & (Connection.target_id == user_id)) |
        ((Connection.user_id == user_id) & (Connection.target_id == current_user.id))
    ).first()

    return render_template('main/profile.html', user=user, user_tags=user_tags, connection=connection)


@bp.route('/profile/avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # Open and process image
        img = Image.open(file.stream)
        
        # Convert to RGB if necessary (e.g. for RGBA/PNG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Resize to 256x256 (crop if necessary)
        img.thumbnail((512, 512), Image.LANCZOS)
        
        # Center crop to square
        width, height = img.size
        new_size = min(width, height)
        left = (width - new_size) / 2
        top = (height - new_size) / 2
        right = (width + new_size) / 2
        bottom = (height + new_size) / 2
        img = img.crop((left, top, right, bottom))
        img = img.resize((256, 256), Image.LANCZOS)

        # Compress to bytes
        img_io = io.BytesIO()
        img.save(img_io, format='WebP', quality=85)
        img_data = img_io.getvalue()

        # Encrypt and save
        user_id = current_user.id
        file_path = get_avatar_path(user_id)
        encrypt_and_save(img_data, file_path)

        # Update profile
        if not current_user.profile:
            profile = Profile(user_id=user_id)
            db.session.add(profile)
            db.session.flush()
        
        current_user.profile.avatar_url = file_path
        current_user.profile.avatar_original_filename = file.filename
        db.session.commit()

        return jsonify({'message': 'Avatar updated successfully', 'url': url_for('main.get_avatar', user_id=user_id)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to process image: {str(e)}'}), 500


@bp.route('/profile/avatar/<int:user_id>')
@login_required
def get_avatar(user_id):
    user = db.session.get(User, user_id)
    if not user or not user.profile or not user.profile.avatar_url:
        return redirect(url_for('static', filename='img/default-avatar.png'))

    try:
        decrypted_data = decrypt_and_read(user.profile.avatar_url)
        return decrypted_data, 200, {'Content-Type': 'image/webp', 'Cache-Control': 'public, max-age=86400'}
    except Exception:
        return redirect(url_for('static', filename='img/default-avatar.png'))


@bp.route('/settings')
@login_required
def settings():
    user_tags = db.session.query(Tag).join(UserTag).filter(UserTag.user_id == current_user.id).all()
    return render_template('main/settings.html', user_tags=user_tags)


@bp.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    data = request.form
    if not current_user.profile:
        profile = Profile(user_id=current_user.id)
        db.session.add(profile)
    else:
        profile = current_user.profile

    # Update basic info
    profile.full_name = data.get('full_name', profile.full_name)
    profile.bio = data.get('bio', profile.bio)
    profile.company = data.get('company', profile.company)
    profile.title = data.get('title', profile.title)
    profile.location = data.get('location', profile.location)
    profile.graduation_year = data.get('graduation_year', profile.graduation_year)
    profile.linkedin_url = data.get('linkedin_url', profile.linkedin_url)
    profile.github_url = data.get('github_url', profile.github_url)
    
    # Real-world fields
    profile.first_name = data.get('first_name', profile.first_name)
    profile.last_name = data.get('last_name', profile.last_name)
    profile.phone = data.get('phone', profile.phone)
    profile.alternate_email = data.get('alternate_email', profile.alternate_email)
    profile.industry = data.get('industry', profile.industry)
    profile.specialization = data.get('specialization', profile.specialization)
    profile.portfolio_url = data.get('portfolio_url', profile.portfolio_url)
    
    # Checkbox fields
    profile.is_mentor_available = 'is_mentor_available' in data
    profile.is_open_to_connect = 'is_open_to_connect' in data
    profile.is_profile_public = 'is_profile_public' in data

    # Skills handling
    skills_str = data.get('skills', '')
    if skills_str:
        # Clear existing skill tags
        from app.models import UserTag
        UserTag.query.filter_by(user_id=current_user.id).delete()
        
        # Add new ones
        skills = [s.strip().lower() for s in skills_str.split(',') if s.strip()]
        for s_name in skills:
            tag = Tag.query.filter_by(name=s_name, type='skill').first()
            if not tag:
                tag = Tag(name=s_name, type='skill')
                db.session.add(tag)
                db.session.flush()
            
            ut = UserTag(user_id=current_user.id, tag_id=tag.id)
            db.session.add(ut)

    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('main.profile'))

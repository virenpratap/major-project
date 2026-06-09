from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.auth import bp
from app.extensions import db
from app.models import User, Profile, Department, Batch
from datetime import datetime, timezone


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if not current_user.is_approved:
            return redirect(url_for('auth.lobby'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Your account has been deactivated. Contact admin.', 'danger')
                return render_template('auth/login.html')

            # Track login
            user.last_login_at = datetime.now(timezone.utc)
            user.last_login_ip = request.remote_addr or ''
            user.login_count = (user.login_count or 0) + 1
            db.session.commit()

            login_user(user, remember=request.form.get('remember'))

            if not user.is_approved:
                return redirect(url_for('auth.lobby'))

            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    # Fetch departments for the form
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'student')
        phone = request.form.get('phone', '').strip()
        department_id = request.form.get('department_id', '')
        enrollment_number = request.form.get('enrollment_number', '').strip()
        graduation_year = request.form.get('graduation_year', '')

        # Validation
        errors = []
        if not email or not username or not password:
            errors.append('All fields are required.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if role not in ('student', 'alumni', 'faculty'):
            errors.append('Invalid role selected.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html', departments=departments)

        # Create user — NOT approved yet
        user = User(
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            is_approved=False  # Requires admin approval
        )
        db.session.add(user)
        db.session.flush()

        # Parse name parts
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        # Create profile with all available fields
        profile = Profile(
            user_id=user.id,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            enrollment_number=enrollment_number,
        )

        # Set department if provided
        if department_id:
            try:
                profile.department_id = int(department_id)
            except (ValueError, TypeError):
                pass

        # Set graduation year
        if graduation_year:
            try:
                profile.graduation_year = int(graduation_year)
            except (ValueError, TypeError):
                pass

        db.session.add(profile)
        db.session.commit()

        # Notify admins about pending approval
        try:
            from core.notifications import send_notification
            from app.models import User as UserModel
            admins = UserModel.query.filter_by(role='admin', is_active=True).all()
            for admin in admins:
                send_notification(admin.id, 'pending_approval', {
                    'user_id': user.id,
                    'username': username,
                    'full_name': full_name,
                    'role': role,
                    'message': f'{full_name} ({role}) has registered and is awaiting approval.'
                })
        except Exception:
            pass

        login_user(user)
        flash('Registration submitted! Your account is awaiting admin approval.', 'info')
        return redirect(url_for('auth.lobby'))

    return render_template('auth/register.html', departments=departments)


@bp.route('/lobby')
@login_required
def lobby():
    """Waiting room for unapproved users."""
    if current_user.is_approved:
        return redirect(url_for('main.dashboard'))
    return render_template('auth/lobby.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

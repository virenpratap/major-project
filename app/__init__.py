from flask import Flask, redirect, url_for, request
from config import Config
from app.extensions import db, socketio, login_manager
from datetime import timedelta, timezone
import os

# IST timezone constant
IST = timezone(timedelta(hours=5, minutes=30))


def create_app(config_class=Config):
    """Application factory pattern."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app, async_mode='eventlet', cors_allowed_origins='*')
    login_manager.init_app(app)

    # User loader for Flask-Login
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ── Jinja2 IST timezone filter ──
    @app.template_filter('to_ist')
    def to_ist_filter(dt):
        """Convert UTC datetime to IST string."""
        if dt is None:
            return ''
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime('%d %b %Y, %I:%M %p IST')

    @app.template_filter('to_ist_short')
    def to_ist_short_filter(dt):
        """Short IST format for compact views."""
        if dt is None:
            return ''
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime('%d %b, %I:%M %p')

    @app.template_filter('to_ist_date')
    def to_ist_date_filter(dt):
        """Date-only IST format."""
        if dt is None:
            return ''
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime('%d %b %Y')

    # ── Lobby redirect for unapproved users ──
    @app.before_request
    def check_approval():
        """Redirect unapproved users to the lobby page."""
        from flask_login import current_user
        if current_user.is_authenticated and not current_user.is_approved:
            allowed_endpoints = {'auth.lobby', 'auth.logout', 'static'}
            if request.endpoint and request.endpoint not in allowed_endpoints:
                return redirect(url_for('auth.lobby'))

    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.social import bp as social_bp
    app.register_blueprint(social_bp)

    from app.resume import bp as resume_bp
    app.register_blueprint(resume_bp)

    from app.referral import bp as referral_bp
    app.register_blueprint(referral_bp)

    from app.chat import bp as chat_bp
    app.register_blueprint(chat_bp)

    from app.recommend import bp as recommend_bp
    app.register_blueprint(recommend_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.api import bp as api_bp
    app.register_blueprint(api_bp)

    from app.events import bp as events_bp
    app.register_blueprint(events_bp)

    from app.mentorship import bp as mentorship_bp
    app.register_blueprint(mentorship_bp)

    # Import WebSocket event handlers
    from app.chat import events  # noqa: F401

    # Create database tables
    with app.app_context():
        db.create_all()
        _ensure_storage_dirs(app)
        _init_model_weights()
        _ensure_admin_exists()

    # Start background workers
    from core.workers import start_workers
    start_workers(app)

    return app


def _ensure_storage_dirs(app):
    """Create storage directories if they don't exist."""
    storage_path = app.config.get('STORAGE_PATH', 'storage')
    os.makedirs(os.path.join(storage_path, 'users'), exist_ok=True)


def _init_model_weights():
    """Initialize default model weights if not present."""
    from app.models import ModelWeight
    import json

    defaults = {
        'referral_ranking': {
            'skill_match': 0.4,
            'experience': 0.2,
            'projects': 0.2,
            'ats_score': 0.2
        },
        'feed_ranking': {
            'relevance': 0.4,
            'connection_strength': 0.3,
            'recency': 0.2,
            'engagement': 0.1
        }
    }

    for context, weights in defaults.items():
        existing = ModelWeight.query.filter_by(context=context).first()
        if not existing:
            mw = ModelWeight(context=context, weights_json=json.dumps(weights))
            db.session.add(mw)

    db.session.commit()


def _ensure_admin_exists():
    """Create a default admin user if none exists."""
    from app.models import User, Profile
    from werkzeug.security import generate_password_hash

    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(
            email='admin@alumni.net',
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            is_active=True,
            is_approved=True  # Admin is auto-approved
        )
        db.session.add(admin)
        db.session.flush()
        profile = Profile(user_id=admin.id, full_name='System Administrator',
                          first_name='System', last_name='Administrator')
        db.session.add(profile)
        db.session.commit()

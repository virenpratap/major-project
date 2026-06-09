from datetime import datetime, timezone
from flask_login import UserMixin
from app.extensions import db
import json


# ───────────────────────────── AUTH ─────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # admin, student, alumni, faculty
    is_active = db.Column(db.Boolean, default=True)

    # ── Registration Approval ──
    is_approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, default='')

    # ── Login Tracking ──
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), default='')
    login_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    profile = db.relationship('Profile', backref='user', uselist=False, cascade='all, delete-orphan')
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    resumes = db.relationship('Resume', backref='owner', lazy='dynamic')
    notifications = db.relationship('Notification', backref='recipient', lazy='dynamic',
                                    foreign_keys='Notification.user_id')
    approver = db.relationship('User', remote_side=[id], foreign_keys=[approved_by])

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


# ───────────────────────── DEPARTMENT & BATCH ─────────────────────────

class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)                   # e.g. "Computer Science & Engineering"
    code = db.Column(db.String(20), unique=True, nullable=False)       # e.g. "CSE"
    description = db.Column(db.Text, default='')
    head_name = db.Column(db.String(128), default='')                  # HOD name
    head_email = db.Column(db.String(120), default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    batches = db.relationship('Batch', backref='department', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Department {self.code}>'


class Batch(db.Model):
    __tablename__ = 'batches'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)                       # Graduation year e.g. 2026
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    section = db.Column(db.String(10), default='')                     # e.g. "A", "B"
    total_strength = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    is_passed_out = db.Column(db.Boolean, default=False)
    passed_out_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('year', 'department_id', 'section', name='uq_batch'),)

    def __repr__(self):
        return f'<Batch {self.year}-{self.department.code if self.department else "?"}>'


# ───────────────────────────── PROFILE ─────────────────────────────

class Profile(db.Model):
    __tablename__ = 'profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    # ── Personal ──
    full_name = db.Column(db.String(128), default='')
    first_name = db.Column(db.String(64), default='')
    last_name = db.Column(db.String(64), default='')
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), default='')                      # male, female, other, prefer_not_to_say
    phone = db.Column(db.String(20), default='')
    alternate_email = db.Column(db.String(120), default='')
    blood_group = db.Column(db.String(5), default='')                  # A+, B-, O+, AB+ etc.

    # ── Avatar / Profile Picture ──
    avatar_url = db.Column(db.String(512), default='')                 # encrypted file reference
    avatar_original_filename = db.Column(db.String(256), default='')

    # ── Academic ──
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id'), nullable=True)
    enrollment_number = db.Column(db.String(30), default='')           # Roll number / University ID
    enrollment_year = db.Column(db.Integer, nullable=True)             # Year of admission
    graduation_year = db.Column(db.Integer, nullable=True)
    current_semester = db.Column(db.Integer, nullable=True)            # For current students
    degree = db.Column(db.String(64), default='')                      # B.Tech, M.Tech, MBA, PhD
    specialization = db.Column(db.String(128), default='')             # e.g. "Artificial Intelligence"
    cgpa = db.Column(db.Float, nullable=True)

    # ── Professional ──
    bio = db.Column(db.Text, default='')
    company = db.Column(db.String(128), default='')
    title = db.Column(db.String(128), default='')                      # Job title / designation
    industry = db.Column(db.String(64), default='')                    # e.g. "Technology", "Finance"
    experience_years = db.Column(db.Integer, nullable=True)
    current_ctc = db.Column(db.String(30), default='')                 # Optional, for analytics
    location = db.Column(db.String(128), default='')                   # Current city

    # ── Address ──
    address_line1 = db.Column(db.String(256), default='')
    address_line2 = db.Column(db.String(256), default='')
    city = db.Column(db.String(64), default='')
    state = db.Column(db.String(64), default='')
    pincode = db.Column(db.String(10), default='')
    country = db.Column(db.String(64), default='India')

    # ── Social Links ──
    linkedin_url = db.Column(db.String(256), default='')
    github_url = db.Column(db.String(256), default='')
    twitter_url = db.Column(db.String(256), default='')
    portfolio_url = db.Column(db.String(256), default='')
    personal_website = db.Column(db.String(256), default='')

    # ── Preferences ──
    is_mentor_available = db.Column(db.Boolean, default=False)
    is_open_to_connect = db.Column(db.Boolean, default=True)
    is_profile_public = db.Column(db.Boolean, default=True)
    email_notifications = db.Column(db.Boolean, default=True)

    # ── Achievements ──
    achievements = db.Column(db.Text, default='')                      # JSON list
    certifications = db.Column(db.Text, default='')                    # JSON list
    publications = db.Column(db.Text, default='')                      # JSON list

    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    department = db.relationship('Department', backref='profiles')
    batch = db.relationship('Batch', backref='profiles')


# ───────────────────────────── TAGS ─────────────────────────────

class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, index=True)
    type = db.Column(db.String(32), nullable=False, default='skill')  # skill, company, college, job_title, hashtag
    usage_count = db.Column(db.Integer, default=0)

    __table_args__ = (db.UniqueConstraint('name', 'type', name='uq_tag_name_type'),)


class UserTag(db.Model):
    __tablename__ = 'user_tags'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('user_id', 'tag_id', name='uq_user_tag'),)


# ──────────────────────── SOCIAL NETWORK ────────────────────────

class Post(db.Model):
    __tablename__ = 'posts'

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    post_type = db.Column(db.String(20), default='normal')            # normal, announcement, event_share
    scope = db.Column(db.String(20), default='global')                # global, department
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    image_url = db.Column(db.String(512), default='')                 # Attached image (encrypted path)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    likes = db.relationship('PostLike', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    tags = db.relationship('PostTag', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    department = db.relationship('Department', backref='posts')

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def comment_count(self):
        return self.comments.count()


class PostLike(db.Model):
    __tablename__ = 'post_likes'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', name='uq_post_like'),)


class Comment(db.Model):
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship('User', backref='comments')
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side='Comment.id'), lazy='dynamic')


class PostTag(db.Model):
    __tablename__ = 'post_tags'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), nullable=False)

    __table_args__ = (db.UniqueConstraint('post_id', 'tag_id', name='uq_post_tag'),)


class Connection(db.Model):
    __tablename__ = 'connections'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    requester = db.relationship('User', foreign_keys=[user_id], backref='sent_connections')
    target = db.relationship('User', foreign_keys=[target_id], backref='received_connections')

    __table_args__ = (db.UniqueConstraint('user_id', 'target_id', name='uq_connection'),)


class Follow(db.Model):
    __tablename__ = 'follows'

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    followee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    follower = db.relationship('User', foreign_keys=[follower_id], backref='following')
    followee = db.relationship('User', foreign_keys=[followee_id], backref='followers')

    __table_args__ = (db.UniqueConstraint('follower_id', 'followee_id', name='uq_follow'),)


# ─────────────────────────── RESUME ─────────────────────────────

class Resume(db.Model):
    __tablename__ = 'resumes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)  # encrypted path
    file_size = db.Column(db.Integer, default=0)           # original size in bytes
    file_hash = db.Column(db.String(64), default='')       # SHA-256 for dedup
    score = db.Column(db.Float, default=0.0)
    analysis_json = db.Column(db.Text, default='{}')
    is_validated = db.Column(db.Boolean, default=False)     # True if confirmed as resume
    validation_reason = db.Column(db.String(256), default='')
    status = db.Column(db.String(20), default='pending')   # pending, processing, completed, failed, rejected
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def analysis(self):
        try:
            return json.loads(self.analysis_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @analysis.setter
    def analysis(self, data):
        self.analysis_json = json.dumps(data)


# ──────────────────────────── EVENTS ──────────────────────────────

class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, default='')
    event_type = db.Column(db.String(30), nullable=False, default='event')
    # Types: meeting, event, webinar, placement_drive, workshop, hackathon, reunion, announcement

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)

    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(256), default='')
    is_virtual = db.Column(db.Boolean, default=False)
    meeting_link = db.Column(db.String(512), default='')
    max_attendees = db.Column(db.Integer, nullable=True)
    registration_deadline = db.Column(db.DateTime, nullable=True)
    contact_email = db.Column(db.String(120), default='')
    banner_image = db.Column(db.String(512), default='')

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    creator = db.relationship('User', backref='created_events')
    department = db.relationship('Department', backref='events')
    rsvps = db.relationship('EventRSVP', backref='event', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def rsvp_count(self):
        return self.rsvps.filter_by(status='attending').count()


class EventRSVP(db.Model):
    __tablename__ = 'event_rsvps'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='attending')  # attending, maybe, declined
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='event_rsvps')
    __table_args__ = (db.UniqueConstraint('event_id', 'user_id', name='uq_event_rsvp'),)


# ──────────────────────────── JOBS ──────────────────────────────

class Job(db.Model):
    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    company = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(128), default='')
    job_type = db.Column(db.String(32), default='full-time')  # full-time, part-time, internship, contract
    experience_required = db.Column(db.String(30), default='')  # e.g. "0-2 years"
    salary_range = db.Column(db.String(50), default='')
    application_deadline = db.Column(db.DateTime, nullable=True)
    apply_link = db.Column(db.String(512), default='')
    skills_required = db.Column(db.Text, default='[]')  # JSON array
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    poster = db.relationship('User', backref='posted_jobs')
    referrals = db.relationship('Referral', backref='job', lazy='dynamic')

    @property
    def skills_list(self):
        try:
            return json.loads(self.skills_required)
        except (json.JSONDecodeError, TypeError):
            return []


# ────────────────────────── REFERRALS ───────────────────────────

class Referral(db.Model):
    __tablename__ = 'referrals'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    alumni_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    status = db.Column(db.String(20), default='applied')  # applied, ranked, selected, referred, rejected
    rank = db.Column(db.Integer)
    rank_score = db.Column(db.Float, default=0.0)
    rank_explanation = db.Column(db.Text, default='{}')
    referral_message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    student = db.relationship('User', foreign_keys=[student_id], backref='student_referrals')
    alumni = db.relationship('User', foreign_keys=[alumni_id], backref='alumni_referrals')


# ────────────────────────── MENTORSHIP ───────────────────────────

class MentorshipRequest(db.Model):
    __tablename__ = 'mentorship_requests'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected, completed
    rejection_reason = db.Column(db.Text, default='')
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    student = db.relationship('User', foreign_keys=[student_id], backref='sent_mentorship_requests')
    mentor = db.relationship('User', foreign_keys=[mentor_id], backref='received_mentorship_requests')

    __table_args__ = (db.UniqueConstraint('student_id', 'mentor_id', status, name='uq_mentorship_request_active'),)


# ──────────────────────────── CHAT ──────────────────────────────

class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    room = db.Column(db.String(128), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    sender = db.relationship('User', backref='sent_messages')


class ChatGroup(db.Model):
    __tablename__ = 'chat_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    creator = db.relationship('User', backref='created_groups')
    members = db.relationship('ChatGroupMember', backref='group', cascade='all, delete-orphan')


class ChatGroupMember(db.Model):
    __tablename__ = 'chat_group_members'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('chat_groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='uq_group_member'),)


# ───────────────────────── NOTIFICATIONS ────────────────────────

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(32), nullable=False)
    data = db.Column(db.Text, default='{}')  # JSON
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def data_json(self):
        try:
            return json.loads(self.data) if self.data else {}
        except (json.JSONDecodeError, TypeError):
            return {}


# ──────────────────────── ML / ADAPTIVE ─────────────────────────

class ModelWeight(db.Model):
    __tablename__ = 'model_weights'

    id = db.Column(db.Integer, primary_key=True)
    context = db.Column(db.String(64), unique=True, nullable=False)
    weights_json = db.Column(db.Text, default='{}')
    version = db.Column(db.Integer, default=1)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    @property
    def weights(self):
        try:
            return json.loads(self.weights_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    @weights.setter
    def weights(self, data):
        self.weights_json = json.dumps(data)


# ───────────────────────── JOB QUEUE ────────────────────────────

class JobQueue(db.Model):
    __tablename__ = 'jobs_queue'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    payload = db.Column(db.Text, default='{}')
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    retries = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    error_message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


# ────────────────────────── AUDIT LOG ───────────────────────────

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(128), nullable=False)
    target = db.Column(db.String(256), default='')
    details = db.Column(db.Text, default='')
    ip_address = db.Column(db.String(45), default='')
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    actor = db.relationship('User', backref='audit_actions')


# ───────────────────────── LLM LOGS ─────────────────────────────

class LLMLog(db.Model):
    __tablename__ = 'llm_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, default='')
    model = db.Column(db.String(64), default='')
    tokens_used = db.Column(db.Integer, default=0)
    duration_ms = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

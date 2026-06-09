"""
Adaptive recommendation engine.
Recommends jobs, people, and mentors based on multiple signals.
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def recompute_recommendations(payload):
    """Recompute recommendations when profile is updated."""
    user_id = payload.get('user_id')
    logger.info(f"Recomputing recommendations for user {user_id}")
    # Recommendations are computed on-demand in get_recommendations
    # This event handler could pre-cache them in future


def get_recommendations(user_id, rec_type='all', limit=10):
    """Get personalized recommendations for a user.

    Args:
        user_id: target user ID
        rec_type: 'jobs', 'people', 'mentors', or 'all'
        limit: max results per type

    Returns:
        dict with recommendation lists
    """
    results = {}

    try:
        if rec_type in ('all', 'jobs'):
            results['jobs'] = _recommend_jobs(user_id, limit)

        if rec_type in ('all', 'people'):
            results['people'] = _recommend_people(user_id, limit)

        if rec_type in ('all', 'mentors'):
            results['mentors'] = _recommend_mentors(user_id, limit)
    except Exception as e:
        logger.error(f"Recommendation failed: {e}")
        results = {'jobs': [], 'people': [], 'mentors': []}

    return results


def _recommend_jobs(user_id, limit):
    """Recommend jobs based on skill overlap and preferences."""
    from app.extensions import db
    from app.models import Job, UserTag, Tag
    from core.nlp_utils import cosine_similarity, generate_embedding

    # Get user's skills
    user_tags = db.session.query(Tag).join(UserTag).filter(
        UserTag.user_id == user_id, Tag.type == 'skill'
    ).all()
    user_skills = set(t.name.lower() for t in user_tags)

    # Get active jobs
    jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(50).all()

    scored = []
    for job in jobs:
        job_skills = set(s.lower() for s in job.skills_list)

        # Skill overlap score
        if user_skills and job_skills:
            overlap = len(user_skills & job_skills)
            total = len(user_skills | job_skills)
            score = overlap / max(total, 1)
        else:
            score = 0.1  # Base score

        scored.append({
            'id': job.id,
            'title': job.title,
            'company': job.company,
            'location': job.location,
            'type': job.job_type,
            'score': round(score, 2),
            'matching_skills': list(user_skills & job_skills) if user_skills else [],
            'created_at': job.created_at.isoformat()
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:limit]


def _recommend_people(user_id, limit):
    """Recommend people to connect with based on shared interests and network."""
    from app.extensions import db
    from app.models import User, Profile, UserTag, Tag, Connection

    # Get user's skills
    user_tag_ids = set(ut.tag_id for ut in UserTag.query.filter_by(user_id=user_id).all())

    # Get existing connections
    existing_connections = set()
    connections = Connection.query.filter(
        (Connection.user_id == user_id) | (Connection.target_id == user_id)
    ).all()
    for c in connections:
        existing_connections.add(c.user_id if c.target_id == user_id else c.target_id)

    # Score other users
    users = User.query.filter(
        User.id != user_id,
        User.is_active == True,
        User.id.notin_(existing_connections) if existing_connections else True
    ).limit(100).all()

    scored = []
    for user in users:
        other_tag_ids = set(ut.tag_id for ut in UserTag.query.filter_by(user_id=user.id).all())

        # Tag overlap
        if user_tag_ids and other_tag_ids:
            overlap = len(user_tag_ids & other_tag_ids)
            total = len(user_tag_ids | other_tag_ids)
            score = overlap / max(total, 1)
        else:
            score = 0.05

        profile = user.profile
        scored.append({
            'id': user.id,
            'username': user.username,
            'name': profile.full_name if profile else user.username,
            'role': user.role,
            'title': profile.title if profile else '',
            'company': profile.company if profile else '',
            'score': round(score, 2),
            'shared_tags': len(user_tag_ids & other_tag_ids) if user_tag_ids else 0
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:limit]


def _recommend_mentors(user_id, limit):
    """Recommend alumni mentors based on career alignment."""
    from app.extensions import db
    from app.models import User, Profile, UserTag, Tag

    # Get user's skills and interests
    user_tag_ids = set(ut.tag_id for ut in UserTag.query.filter_by(user_id=user_id).all())

    # Get alumni users
    alumni = User.query.filter_by(role='alumni', is_active=True).limit(50).all()

    scored = []
    for alum in alumni:
        alum_tag_ids = set(ut.tag_id for ut in UserTag.query.filter_by(user_id=alum.id).all())

        if user_tag_ids and alum_tag_ids:
            overlap = len(user_tag_ids & alum_tag_ids)
            score = overlap / max(len(user_tag_ids), 1)
        else:
            score = 0.1

        profile = alum.profile
        scored.append({
            'id': alum.id,
            'username': alum.username,
            'name': profile.full_name if profile else alum.username,
            'title': profile.title if profile else '',
            'company': profile.company if profile else '',
            'score': round(score, 2),
            'expertise_match': len(user_tag_ids & alum_tag_ids) if user_tag_ids else 0
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:limit]

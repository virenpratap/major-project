"""
Explainable candidate ranking engine for referrals.
Uses weighted multi-factor scoring with adaptive weights.
"""
import json
import logging
from core.nlp_utils import cosine_similarity, extract_skills, generate_embedding

logger = logging.getLogger(__name__)


def rank_candidates(payload):
    """Rank candidates for a referral job.

    Triggered by 'referral_requested' event.
    """
    job_id = payload.get('job_id')

    logger.info(f"Ranking candidates for job {job_id}")

    try:
        from app.extensions import db
        from app.models import Referral, Job, Resume, User, ModelWeight

        job = db.session.get(Job, job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Get adaptive weights
        weight_record = ModelWeight.query.filter_by(context='referral_ranking').first()
        if weight_record:
            weights = weight_record.weights
        else:
            weights = {'skill_match': 0.4, 'experience': 0.2, 'projects': 0.2, 'ats_score': 0.2}

        # Get all referrals (candidates) for this job
        referrals = Referral.query.filter_by(job_id=job_id, status='applied').all()

        if not referrals:
            logger.info(f"No candidates for job {job_id}")
            return

        # Job requirements
        job_skills = set(s.lower() for s in job.skills_list)
        job_description = job.description

        scored_candidates = []

        for referral in referrals:
            # Get latest resume
            resume = Resume.query.filter_by(
                user_id=referral.student_id,
                status='completed'
            ).order_by(Resume.created_at.desc()).first()

            if not resume or not resume.analysis:
                # No resume data - minimal score
                scored_candidates.append({
                    'referral': referral,
                    'score': 10.0,
                    'explanation': {
                        'skill_match': 0, 'experience': 0,
                        'projects': 0, 'ats_score': 0,
                        'note': 'No resume data available'
                    }
                })
                continue

            analysis = resume.analysis

            # Factor 1: Skill Match (0-1)
            candidate_skills = set(s.lower() for s in analysis.get('skills', []))
            if job_skills:
                skill_overlap = len(job_skills & candidate_skills) / len(job_skills)
            else:
                skill_overlap = min(len(candidate_skills) / 10, 1.0)

            # Factor 2: Experience (0-1)
            exp_years = analysis.get('experience_years', 0)
            experience_score = min(exp_years / 5, 1.0)  # 5 years = max

            # Factor 3: Projects/Content Quality (0-1)
            sections = analysis.get('sections_found', [])
            has_projects = 'projects' in [s.lower() for s in sections]
            content_score = 0.5
            if has_projects:
                content_score += 0.3
            if analysis.get('word_count', 0) > 300:
                content_score += 0.2
            content_score = min(content_score, 1.0)

            # Factor 4: ATS Score (0-1)
            ats_normalized = analysis.get('ats_score', 0) / 100

            # Compute weighted final score
            final_score = (
                weights['skill_match'] * skill_overlap +
                weights['experience'] * experience_score +
                weights['projects'] * content_score +
                weights['ats_score'] * ats_normalized
            ) * 100

            scored_candidates.append({
                'referral': referral,
                'score': round(final_score, 1),
                'explanation': {
                    'skill_match': round(skill_overlap, 2),
                    'experience': round(experience_score, 2),
                    'projects': round(content_score, 2),
                    'ats_score': round(ats_normalized, 2)
                }
            })

        # Sort by score descending
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)

        # Update rankings in DB
        for rank, item in enumerate(scored_candidates, 1):
            ref = item['referral']
            ref.rank = rank
            ref.rank_score = item['score']
            ref.rank_explanation = json.dumps(item['explanation'])
            ref.status = 'ranked'

        db.session.commit()

        # Publish event
        from core.event_bus import publish
        publish('candidates_ranked', {
            'job_id': job_id,
            'count': len(scored_candidates)
        })

        logger.info(f"Ranked {len(scored_candidates)} candidates for job {job_id}")

    except Exception as e:
        logger.error(f"Ranking failed: {e}")
        raise


def update_weights_from_feedback(job_id, selected_referral_id):
    """Adaptive weight update based on alumni selection feedback.

    If the selected candidate wasn't top-ranked, adjust weights
    to better reflect alumni preferences.
    """
    try:
        from app.extensions import db
        from app.models import Referral, ModelWeight

        selected = db.session.get(Referral, selected_referral_id)
        if not selected or not selected.rank:
            return

        # If selection matches top rank, weights are good
        if selected.rank == 1:
            return

        # Get the top-ranked candidate's explanation
        top_ranked = Referral.query.filter_by(
            job_id=job_id, rank=1
        ).first()

        if not top_ranked:
            return

        selected_exp = json.loads(selected.rank_explanation) if selected.rank_explanation else {}
        top_exp = json.loads(top_ranked.rank_explanation) if top_ranked.rank_explanation else {}

        # Update weights: increase factors where selected > top, decrease where selected < top
        weight_record = ModelWeight.query.filter_by(context='referral_ranking').first()
        if not weight_record:
            return

        weights = weight_record.weights
        learning_rate = 0.02

        for factor in ['skill_match', 'experience', 'projects', 'ats_score']:
            sel_val = selected_exp.get(factor, 0)
            top_val = top_exp.get(factor, 0)

            if sel_val > top_val:
                weights[factor] = min(weights[factor] + learning_rate, 0.6)
            elif sel_val < top_val:
                weights[factor] = max(weights[factor] - learning_rate, 0.1)

        # Normalize weights to sum to 1
        total = sum(weights.values())
        weights = {k: round(v / total, 3) for k, v in weights.items()}

        weight_record.weights = weights
        weight_record.version += 1
        db.session.commit()

        logger.info(f"Weights updated: {weights}")

    except Exception as e:
        logger.error(f"Weight update failed: {e}")

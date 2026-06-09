"""
Resume processing pipeline:
1. Extract text from PDF/DOCX
2. NLP analysis (skills, education, experience)
3. ATS scoring
4. AI feedback generation
5. Store results
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def process_resume(payload):
    """Main resume processing pipeline triggered by resume_uploaded event."""
    resume_id = payload.get('resume_id')
    user_id = payload.get('user_id')

    logger.info(f"Processing resume {resume_id} for user {user_id}")

    try:
        from app.extensions import db
        from app.models import Resume
        from core.encryption import decrypt_and_read
        from core.nlp_utils import (
            extract_skills, extract_education, extract_experience,
            detect_ats_sections, compute_ats_score, generate_embedding,
            validate_is_resume
        )
        from core.ai_client import complete
        from core.notifications import notify_resume_ready

        # Get resume record
        resume = db.session.get(Resume, resume_id)
        if not resume:
            logger.error(f"Resume {resume_id} not found")
            return

        resume.status = 'processing'
        db.session.commit()

        # Step 1: Decrypt and extract text
        encrypted_data = decrypt_and_read(resume.file_path)
        text = extract_text(encrypted_data, resume.filename)

        if not text.strip():
            resume.status = 'failed'
            resume.analysis = {'error': 'Could not extract text from file'}
            db.session.commit()
            return

        # Step 1.5: Validate this is actually a resume
        validation = validate_is_resume(text)
        resume.is_validated = validation['is_resume']
        resume.validation_reason = (
            f"Confidence: {validation['confidence']:.0%} — "
            f"Signals: {', '.join(validation['signals_found']) or 'none'}"
        )

        if not validation['is_resume']:
            resume.status = 'rejected'
            resume.analysis = {
                'error': 'The uploaded file does not appear to be a resume.',
                'validation': validation
            }
            db.session.commit()
            from core.notifications import send_notification
            send_notification(user_id, 'resume_rejected', {
                'resume_id': resume_id,
                'message': 'Your upload was rejected — it does not appear to be a resume. '
                           'Please upload a valid resume (PDF/DOCX) with your contact info, '
                           'education, experience, and skills.'
            })
            logger.info(f"Resume {resume_id} rejected: not a valid resume (confidence={validation['confidence']})")
            return

        # Step 2: NLP Analysis
        skills = extract_skills(text)
        education = extract_education(text)
        experience_years = extract_experience(text)
        sections_found, sections_missing = detect_ats_sections(text)

        # Step 3: ATS Scoring
        ats_score = compute_ats_score(text, skills, sections_found, sections_missing)

        # Step 4: Generate embedding for similarity matching
        embedding = generate_embedding(text)

        # Step 5: AI feedback (async-safe)
        ai_feedback = ""
        try:
            ai_feedback = complete(
                f"""Analyze this resume and provide actionable feedback:

Resume Text:
{text[:3000]}

Extracted Skills: {', '.join(skills[:20])}
ATS Score: {ats_score}/100
Sections Found: {', '.join(sections_found)}
Missing Sections: {', '.join(sections_missing[:5])}

Provide:
1. Overall assessment (2-3 sentences)
2. Top 3 strengths
3. Top 3 areas for improvement
4. ATS optimization tips""",
                system_prompt="You are an expert resume reviewer and ATS optimization specialist."
            )
        except Exception as e:
            logger.warning(f"AI feedback failed: {e}")
            ai_feedback = "AI feedback unavailable. See ATS analysis for details."

        # Step 6: Store results
        analysis = {
            'skills': skills,
            'education': education,
            'experience_years': experience_years,
            'sections_found': sections_found,
            'sections_missing': sections_missing,
            'ats_score': ats_score,
            'ai_feedback': ai_feedback,
            'word_count': len(text.split()),
            'processed_at': datetime.now(timezone.utc).isoformat()
        }

        resume.score = ats_score
        resume.analysis = analysis
        resume.status = 'completed'
        db.session.commit()

        # Step 7: Notify user
        notify_resume_ready(user_id, resume_id, ats_score)

        # Step 8: Publish processed event
        from core.event_bus import publish
        publish('resume_processed', {'resume_id': resume_id, 'user_id': user_id, 'score': ats_score})

        logger.info(f"Resume {resume_id} processed successfully. Score: {ats_score}")

    except Exception as e:
        logger.error(f"Resume processing failed: {e}")
        try:
            from app.extensions import db
            from app.models import Resume
            resume = db.session.get(Resume, resume_id)
            if resume:
                resume.status = 'failed'
                resume.analysis = {'error': str(e)}
                db.session.commit()
        except Exception:
            pass


def extract_text(file_data, filename):
    """Extract text from PDF or DOCX file data."""
    filename_lower = filename.lower()

    if filename_lower.endswith('.pdf'):
        return _extract_pdf_text(file_data)
    elif filename_lower.endswith('.docx'):
        return _extract_docx_text(file_data)
    elif filename_lower.endswith('.txt'):
        return file_data.decode('utf-8', errors='ignore')
    else:
        # Try as plain text
        return file_data.decode('utf-8', errors='ignore')


def _extract_pdf_text(file_data):
    """Extract text from PDF bytes."""
    try:
        import io
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_data))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or '')
        return '\n'.join(text_parts)
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ''


def _extract_docx_text(file_data):
    """Extract text from DOCX bytes."""
    try:
        import io
        from docx import Document
        doc = Document(io.BytesIO(file_data))
        text_parts = []
        for para in doc.paragraphs:
            text_parts.append(para.text)
        return '\n'.join(text_parts)
    except Exception as e:
        logger.error(f"DOCX extraction failed: {e}")
        return ''

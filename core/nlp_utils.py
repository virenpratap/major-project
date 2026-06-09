"""
NLP utilities for resume processing.
Uses regex-based skill extraction and keyword matching.
spaCy and sentence-transformers are optional enhancements.
"""
import re
import logging
import math

logger = logging.getLogger(__name__)

# Try to import optional NLP libraries
_nlp = None
_embedder = None


def _get_nlp():
    """Lazy-load spaCy model."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load('en_core_web_sm')
            logger.info("spaCy model loaded")
        except Exception as e:
            logger.warning(f"spaCy not available: {e}")
    return _nlp


def _get_embedder():
    """Lazy-load sentence transformer."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence transformer loaded")
        except Exception as e:
            logger.warning(f"Sentence transformer not available: {e}")
    return _embedder


# ─────────── Common skill keywords ───────────

TECHNICAL_SKILLS = {
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'go', 'rust',
    'react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring', 'express',
    'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
    'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
    'git', 'linux', 'ci/cd', 'jenkins', 'github actions',
    'machine learning', 'deep learning', 'nlp', 'computer vision',
    'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy',
    'html', 'css', 'rest api', 'graphql', 'microservices',
    'agile', 'scrum', 'jira', 'figma', 'photoshop',
    'data analysis', 'data science', 'big data', 'spark', 'hadoop',
    'blockchain', 'iot', 'cybersecurity', 'devops', 'sre'
}

SOFT_SKILLS = {
    'leadership', 'communication', 'teamwork', 'problem solving',
    'project management', 'analytical', 'critical thinking',
    'time management', 'adaptability', 'creativity'
}

ATS_SECTIONS = [
    'summary', 'objective', 'experience', 'work experience',
    'education', 'skills', 'technical skills', 'projects',
    'certifications', 'awards', 'publications', 'references',
    'volunteer', 'interests', 'languages'
]

# ─────────── Resume validation signals ───────────

RESUME_SIGNALS = {
    'contact_email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    'contact_phone': r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
    'linkedin': r'linkedin\.com/in/[\w-]+',
    'section_headers': r'(?i)(?:^|\n)\s*(?:experience|education|skills|summary|objective|projects|certifications|work\s+history)',
    'degree_keywords': r'(?i)\b(?:bachelor|master|phd|doctorate|b\.tech|m\.tech|bsc|msc|mba|b\.e|m\.e|bca|mca|diploma)\b',
    'employment_dates': r'(?i)(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*[\s,]+\d{4}\s*[-–—to]+\s*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*[\s,]+\d{4}|present|current)',
    'action_verbs_dense': r'(?i)\b(?:developed|managed|designed|implemented|created|led|built|achieved|optimized|analyzed|coordinated|delivered|improved|maintained)\b',
}


def validate_is_resume(text):
    """Validate whether the uploaded document is actually a resume.

    Uses heuristic signal detection: at least 3 of 7 signals must be present.

    Returns:
        dict: {'is_resume': bool, 'confidence': float, 'signals_found': list, 'signals_missing': list}
    """
    if not text or len(text.strip()) < 50:
        return {'is_resume': False, 'confidence': 0.0,
                'signals_found': [], 'signals_missing': list(RESUME_SIGNALS.keys())}

    text_check = text[:10000]  # Check first 10k chars
    signals_found = []
    signals_missing = []

    for signal_name, pattern in RESUME_SIGNALS.items():
        matches = re.findall(pattern, text_check)
        if signal_name == 'action_verbs_dense':
            # Require at least 3 action verbs to count
            if len(matches) >= 3:
                signals_found.append(signal_name)
            else:
                signals_missing.append(signal_name)
        elif matches:
            signals_found.append(signal_name)
        else:
            signals_missing.append(signal_name)

    total_signals = len(RESUME_SIGNALS)
    found_count = len(signals_found)
    confidence = found_count / total_signals

    # Need at least 3 signals to pass
    is_resume = found_count >= 3

    return {
        'is_resume': is_resume,
        'confidence': round(confidence, 2),
        'signals_found': signals_found,
        'signals_missing': signals_missing
    }


def extract_skills(text):
    """Extract skills from text using keyword matching and optional NER."""
    text_lower = text.lower()
    found_skills = set()

    # Keyword matching
    for skill in TECHNICAL_SKILLS:
        if skill in text_lower:
            found_skills.add(skill)

    for skill in SOFT_SKILLS:
        if skill in text_lower:
            found_skills.add(skill)

    # spaCy NER for additional entities
    nlp = _get_nlp()
    if nlp:
        try:
            doc = nlp(text[:10000])  # Limit to first 10k chars
            for ent in doc.ents:
                if ent.label_ in ('ORG', 'PRODUCT', 'WORK_OF_ART'):
                    found_skills.add(ent.text.lower())
        except Exception as e:
            logger.warning(f"spaCy NER failed: {e}")

    return list(found_skills)


def extract_education(text):
    """Extract education information from resume text."""
    education = []
    patterns = [
        r'(?i)(bachelor|master|phd|doctorate|associate|b\.\w+|m\.\w+|mba|b\.tech|m\.tech)[\s\S]{0,100}',
        r'(?i)(university|college|institute|school)\s+of\s+[\w\s]+',
        r'(?i)(gpa|cgpa|grade)[\s:]+[\d.]+',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        education.extend(matches)

    return education


def extract_experience(text):
    """Extract years of experience from resume text."""
    patterns = [
        r'(\d+)\+?\s*years?\s+(?:of\s+)?experience',
        r'experience\s*[:]\s*(\d+)\s*years?',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Count unique date ranges as proxy
    date_pattern = r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{4})'
    dates = re.findall(date_pattern, text, re.IGNORECASE)
    if len(dates) >= 2:
        return max(1, len(dates) // 2)

    return 0


def detect_ats_sections(text):
    """Detect which ATS-standard sections are present in the resume."""
    text_lower = text.lower()
    found = []
    missing = []

    for section in ATS_SECTIONS:
        if section in text_lower:
            found.append(section)
        else:
            missing.append(section)

    return found, missing


def compute_ats_score(text, skills_found, sections_found, sections_missing):
    """Compute an ATS compatibility score (0-100)."""
    score = 0.0

    # Section coverage (40 points)
    essential = {'experience', 'education', 'skills'}
    for s in essential:
        if s in [sec.lower() for sec in sections_found]:
            score += 10
    # Bonus for additional sections
    score += min(len(sections_found) - 3, 3) * 3.33 if len(sections_found) > 3 else 0

    # Skills density (30 points)
    skill_score = min(len(skills_found) / 10, 1.0) * 30
    score += skill_score

    # Content quality (20 points)
    # Check for action verbs
    action_verbs = {'developed', 'managed', 'designed', 'implemented', 'created',
                    'led', 'improved', 'increased', 'decreased', 'built',
                    'launched', 'achieved', 'optimized', 'automated', 'analyzed'}
    verb_count = sum(1 for v in action_verbs if v in text.lower())
    score += min(verb_count / 5, 1.0) * 10

    # Check for quantifiable results
    numbers = re.findall(r'\d+%|\$\d+|\d+\s+(?:users|clients|projects)', text)
    score += min(len(numbers) / 3, 1.0) * 10

    # Formatting (10 points)
    word_count = len(text.split())
    if 300 <= word_count <= 1000:
        score += 10
    elif 200 <= word_count <= 1500:
        score += 5

    return round(min(score, 100), 1)


def generate_embedding(text):
    """Generate text embedding using sentence-transformers."""
    embedder = _get_embedder()
    if embedder:
        try:
            return embedder.encode(text[:5000]).tolist()
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")

    # Fallback: simple word frequency vector
    return _simple_embedding(text)


def _simple_embedding(text, dim=64):
    """Simple fallback embedding based on word hashing."""
    words = text.lower().split()
    vector = [0.0] * dim
    for word in words:
        idx = hash(word) % dim
        vector[idx] += 1.0

    # Normalize
    magnitude = math.sqrt(sum(x * x for x in vector))
    if magnitude > 0:
        vector = [x / magnitude for x in vector]

    return vector


def cosine_similarity(vec_a, vec_b):
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)

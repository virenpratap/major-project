"""
NVIDIA Nemotron AI client using OpenAI SDK with base_url override.
Provides both synchronous and streaming completions.
"""
import os
import time
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_client = None
_rate_limiter = {
    'tokens': 10,
    'max_tokens': 10,
    'last_refill': time.time(),
    'window': 60,
    'lock': threading.Lock()
}


def get_client():
    """Get or create the OpenAI client configured for NVIDIA."""
    global _client
    if _client is None:
        try:
            from openai import OpenAI
            api_key = os.getenv('NVIDIA_API_KEY', '')
            if api_key and api_key != 'your-nvidia-api-key-here':
                _client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=api_key
                )
                logger.info("NVIDIA AI client initialized")
            else:
                logger.warning("NVIDIA API key not configured, using mock responses")
                _client = None
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            _client = None
    return _client


def _check_rate_limit():
    """Token bucket rate limiter."""
    with _rate_limiter['lock']:
        now = time.time()
        elapsed = now - _rate_limiter['last_refill']
        _rate_limiter['tokens'] = min(
            _rate_limiter['max_tokens'],
            _rate_limiter['tokens'] + elapsed * (_rate_limiter['max_tokens'] / _rate_limiter['window'])
        )
        _rate_limiter['last_refill'] = now

        if _rate_limiter['tokens'] < 1:
            return False
        _rate_limiter['tokens'] -= 1
        return True


def complete(prompt, system_prompt="You are a helpful career assistant.", max_tokens=2048, temperature=0.7):
    """Synchronous completion (for backend jobs like resume analysis)."""
    if not _check_rate_limit():
        logger.warning("Rate limit exceeded for LLM call")
        return "Rate limit exceeded. Please try again later."

    start_time = time.time()
    client = get_client()

    if client is None:
        return _mock_response(prompt)

    try:
        resp = client.chat.completions.create(
            model=os.getenv('NVIDIA_MODEL', 'nvidia/nemotron-3-super-120b-a12b'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            top_p=0.9,
            max_tokens=max_tokens
        )
        text = resp.choices[0].message.content
        duration_ms = int((time.time() - start_time) * 1000)
        tokens_used = getattr(resp.usage, 'total_tokens', 0) if resp.usage else 0

        _log_llm_call(prompt, text, tokens_used, duration_ms)
        return text

    except Exception as e:
        logger.error(f"LLM completion failed: {e}")
        return _mock_response(prompt)


def stream_complete(prompt, system_prompt="You are a helpful career assistant.", max_tokens=4096):
    """Streaming completion (for chat UI with reasoning)."""
    if not _check_rate_limit():
        yield "Rate limit exceeded. Please try again later."
        return

    client = get_client()

    if client is None:
        yield _mock_response(prompt)
        return

    try:
        completion = client.chat.completions.create(
            model=os.getenv('NVIDIA_MODEL', 'nvidia/nemotron-3-super-120b-a12b'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            temperature=0.7,
            top_p=0.95,
            max_tokens=max_tokens,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 16384
            }
        )

        full_response = []
        for chunk in completion:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            # Skip reasoning content
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                continue
            if delta.content is not None:
                full_response.append(delta.content)
                yield delta.content

        _log_llm_call(prompt, ''.join(full_response), 0, 0)

    except Exception as e:
        logger.error(f"Streaming LLM failed: {e}")
        yield _mock_response(prompt)


def _mock_response(prompt):
    """Generate a mock response when API is not available."""
    prompt_lower = prompt.lower()

    if 'resume' in prompt_lower or 'ats' in prompt_lower:
        return """## Resume Analysis

**Overall Score: 75/100**

### Strengths
- Clear professional summary
- Relevant technical skills listed
- Good use of action verbs

### Areas for Improvement
- Add quantifiable achievements (numbers, percentages)
- Include relevant keywords from job descriptions
- Consider adding a projects section

### ATS Compatibility
- Format is generally ATS-friendly
- Ensure consistent date formatting
- Use standard section headers

*Note: This is a demo analysis. Connect your NVIDIA API key for AI-powered insights.*"""

    elif 'referral' in prompt_lower:
        return """Dear Hiring Manager,

I am writing to recommend this candidate for the position. Based on my interaction with them through our alumni network, I can attest to their strong technical skills and professional demeanor.

They have demonstrated excellent problem-solving abilities and a genuine passion for continuous learning. I believe they would be a valuable addition to your team.

Best regards,
[Alumni Name]

*Note: This is a demo referral. Connect your NVIDIA API key for AI-powered generation.*"""

    elif 'skill' in prompt_lower or 'gap' in prompt_lower:
        return """## Skill Gap Analysis

### Current Skills
- Python, JavaScript, SQL

### Recommended Skills to Learn
1. **Cloud Computing** (AWS/GCP) - High demand in market
2. **Docker/Kubernetes** - Essential for modern deployment
3. **Machine Learning** - Growing field with high compensation

### Learning Path
1. Start with cloud fundamentals (2-4 weeks)
2. Practice containerization (1-2 weeks)
3. Take an ML course (4-8 weeks)

*Note: This is a demo analysis. Connect your NVIDIA API key for personalized insights.*"""

    else:
        return """Thank you for your question. I'd be happy to help with career guidance, resume reviews, or professional development advice.

*Note: This is a demo response. Connect your NVIDIA API key for AI-powered assistance.*"""


def _log_llm_call(prompt, response, tokens_used, duration_ms):
    """Log LLM calls to the database for admin monitoring."""
    try:
        from app.extensions import db
        from app.models import LLMLog

        log = LLMLog(
            prompt=prompt[:1000],  # Truncate long prompts
            response=response[:2000],  # Truncate long responses
            model=os.getenv('NVIDIA_MODEL', 'nvidia/nemotron-3-super-120b-a12b'),
            tokens_used=tokens_used,
            duration_ms=duration_ms
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log LLM call: {e}")

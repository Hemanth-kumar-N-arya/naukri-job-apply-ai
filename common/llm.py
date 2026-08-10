"""
Tries Gemini first for screening-answer drafting; if it's out of free-tier
quota (rate-limited or daily-exhausted), automatically falls back to Groq's
free tier instead of stopping the whole run.

Requires at least one of GEMINI_API_KEY or GROQ_API_KEY in your .env file.
Having both means you effectively get two independent free quotas.
"""
from . import gemini
from . import groq_llm

_QUOTA_ERROR_HINTS = ("429", "quota", "rate limit", "resource_exhausted", "exhausted")


def _looks_like_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(hint in text for hint in _QUOTA_ERROR_HINTS)


def draft_answer(question: str, profile_data: dict, job_context: str = "") -> str:
    try:
        return gemini.draft_answer(question, profile_data, job_context)
    except Exception as e:
        if not _looks_like_quota_error(e):
            raise
        print(f"  (Gemini unavailable — {e}. Falling back to Groq...)")
        return groq_llm.draft_answer(question, profile_data, job_context)

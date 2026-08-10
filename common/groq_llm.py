"""
Generates free-text screening answers using Groq's free tier (genuinely
ongoing, no card required, open-source models like Llama). This exists as
a fallback for when Gemini's daily/per-minute free quota is hit.

Get a free key at https://console.groq.com/keys (sign in with email or
Google, no card needed). Add it to your .env file:
    GROQ_API_KEY=your-key-here
"""
import os
from pathlib import Path
from groq import Groq

MODEL = "llama-3.3-70b-versatile"  # solid free-tier model for this kind of drafting task

_SYSTEM_INSTRUCTIONS = """\
You are drafting a short answer to a job-application screening question, in the
voice of the real applicant described below. Rules, no exceptions:

1. Only use facts given in the applicant profile and work history. Never invent
   an employer, tool, certification, number, or claim not present below.
2. If the question asks about something not covered by the profile, write
   exactly: [NEEDS_HUMAN_INPUT: <one line describing what's missing>]
   and nothing else.
3. Keep answers to 2-4 sentences. No generic filler adjectives ("passionate",
   "detail-oriented", "hard-working") unless the applicant's own words use them.
4. Write in first person, plainly, the way the applicant actually described
   themselves -- not marketing copy.
"""

_client = None


def _load_dotenv_key(name: str):
    if os.environ.get(name):
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            os.environ[name] = value.strip()
            return


def _get_client():
    global _client
    if _client is None:
        _load_dotenv_key("GROQ_API_KEY")
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at "
                "https://console.groq.com/keys and add it to your .env file."
            )
        _client = Groq(api_key=key)
    return _client


def draft_answer(question: str, profile_data: dict, job_context: str = "") -> str:
    """Returns a drafted answer, or a string starting with [NEEDS_HUMAN_INPUT: ...]
    if the profile doesn't actually cover what's being asked."""
    client = _get_client()
    prompt = f"""
APPLICANT PROFILE:
{profile_data}

JOB CONTEXT (title/company/description, may be partial):
{job_context}

SCREENING QUESTION:
{question}

Draft the answer now.
"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content.strip()

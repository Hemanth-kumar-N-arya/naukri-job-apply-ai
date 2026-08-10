"""
Generates free-text screening answers using Google's free-tier Gemini API,
via the current `google-genai` SDK (the old `google-generativeai` package is
retired and will 404).

Get a free key at https://aistudio.google.com/apikey (no card required for the
free tier as of writing -- check current limits there, they change).
Set it as an environment variable before running:
    export GEMINI_API_KEY="your-key-here"
"""
import os
from pathlib import Path
from google import genai
from google.genai import types

MODEL = "gemini-flash-latest"  # alias, always points at the current free-tier Flash model

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

def _load_dotenv_key():
    """Reads GEMINI_API_KEY out of a local .env file if the environment
    variable isn't already set. Looks in the project root (two levels up
    from this file: common/gemini.py -> project root)."""
    if os.environ.get("GEMINI_API_KEY"):
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "GEMINI_API_KEY":
            os.environ["GEMINI_API_KEY"] = value.strip()
            return


_client = None


def _get_client():
    global _client
    if _client is None:
        _load_dotenv_key()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Either run "
                "$env:GEMINI_API_KEY=\"your-key\" in PowerShell, or create a .env "
                "file in the project folder (copy .env.example) with your key in it. "
                "Get a free key at https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=key)
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
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTIONS,
        ),
    )
    return resp.text.strip()

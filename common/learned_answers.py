"""
Remembers answers to screening questions you've typed in yourself before,
keyed by a normalized version of the question text, so you're never asked
the same question twice across runs.

Stored as plain JSON at learned_answers.json in the project root. This file
will contain your personal answers (DOB, etc.) once you start using it —
keep it private the same way you'd treat profile.yaml.
"""
import json
import re
from pathlib import Path

_STORE_PATH = Path(__file__).resolve().parent.parent / "learned_answers.json"


def _normalize(question: str) -> str:
    q = question.lower().strip()
    q = re.sub(r"\s+", " ", q)
    q = re.sub(r"[^\w\s]", "", q)  # drop punctuation so minor phrasing differences still match
    return q


def _load() -> dict:
    if not _STORE_PATH.exists():
        return {}
    try:
        return json.loads(_STORE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict):
    _STORE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get_answer(question: str) -> str | None:
    data = _load()
    return data.get(_normalize(question))


def save_answer(question: str, answer: str):
    data = _load()
    data[_normalize(question)] = answer
    _save(data)

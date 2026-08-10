"""Loads and validates the applicant profile from profile.yaml."""
import yaml
from pathlib import Path


class Profile:
    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def load(cls, path: str = "profile.yaml") -> "Profile":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(
                f"{path} not found. Copy profile.yaml and fill in your real details first."
            )
        with p.open() as f:
            data = yaml.safe_load(f)
        cls._validate(data)
        return cls(data)

    @staticmethod
    def _validate(data: dict):
        required_blocking = [
            "total_experience_years",
            "notice_period_days",
            "current_ctc_lpa",
            "expected_ctc_lpa",
            "resume_file_name",
        ]
        missing = [k for k in required_blocking if data.get(k) in (None, "")]
        if missing:
            raise ValueError(
                "profile.yaml is missing required fields before this can run safely: "
                + ", ".join(missing)
                + ". These gate real screening questions — fill them in with your real numbers."
            )

    def __getattr__(self, item):
        if item in self.data:
            return self.data[item]
        raise AttributeError(item)

    def answer_library(self) -> dict:
        """Common recurring screening-question answers, pre-computed once."""
        d = self.data
        return {
            "years_experience": str(d["total_experience_years"]),
            "notice_period": (
                "Immediately available" if d.get("immediately_available")
                else f"{d['notice_period_days']} days"
            ),
            "current_ctc": (
                "Prefer to discuss" if d["ctc_disclosure_policy"] == "negotiable"
                else f"{d['current_ctc_lpa']} LPA"
            ),
            "expected_ctc": (
                "Negotiable" if d["ctc_disclosure_policy"] == "negotiable"
                else f"{d['expected_ctc_lpa']} LPA"
            ),
            "current_city": d["current_city"],
            "relocate": "Yes" if d.get("relocate_cities") else "No",
            "night_shift": "Yes" if d.get("night_shift_ok") else "No",
            "weekend_work": "Yes" if d.get("weekend_ok") else "No",
        }

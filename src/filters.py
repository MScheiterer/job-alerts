import re
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "filters.yaml"

# American postings almost always format location as "City, ST" — this
# catches that regardless of whether the specific city is in the allow-list.
# Checked against a set (not a substring list) so it can't accidentally
# fire on a two-letter fragment inside an unrelated word.
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
US_STATE_CODE_RE = re.compile(r",\s*([A-Z]{2})\b")


def load_filters():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _has_word(keywords, text):
    """Whole-word match, not substring — used for title_include_any so
    "intern" doesn't match inside "internal"/"international". Keywords may
    be multi-word phrases ("working student"), which \\b handles fine on
    both ends."""
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in keywords)


def _has_us_state_code(location):
    m = US_STATE_CODE_RE.search(location)
    return bool(m and m.group(1) in US_STATE_CODES)


def matches(job, cfg):
    title = (job.get("title") or "").lower()

    if not _has_word(cfg["title_include_any"], title):
        return False
    if any(k in title for k in cfg["title_exclude_any"]):
        return False
    if not any(k in title for k in cfg["role_keywords_any"]):
        return False

    location = job.get("location") or ""
    if location:
        if not (
            any(k.lower() in location.lower() for k in cfg["location_include_any"])
            or _has_us_state_code(location)
        ):
            return False
    elif not cfg.get("location_include_if_empty", True):
        return False

    return True


def filter_jobs(jobs, cfg=None):
    cfg = cfg or load_filters()
    return [j for j in jobs if matches(j, cfg)]

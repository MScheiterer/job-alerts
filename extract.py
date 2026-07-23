"""Best-effort regex/keyword extraction of compensation, start date, duration,
and workload from a job posting's description text.

This is heuristic, not a parser — postings phrase these details in wildly
different ways across companies, so it will miss non-standard phrasing.
Structured fields from the source API (e.g. SmartRecruiters' `compensation`
object, Workday's `timeType`) are always preferred over text matches; see
each connector's `enrich()` for where those get set on `job["_compensation"]`
/ `job["_load"]` before this module ever runs.
"""

import html
import re
from datetime import datetime, timezone

NOT_LISTED = "not listed"

CURRENCY = r"(?:USD|EUR|GBP|CHF|US\$|£|€|\$)"
# Digit groups with comma OR apostrophe thousands-separators (the apostrophe
# form — 4'500 — is standard in Swiss postings); a trailing "." only counts
# as part of the number if it's a decimal point followed by more digits —
# otherwise it's just sentence punctuation and shouldn't be swallowed.
NUM = r"\d(?:[\d,']*\d)?(?:\.\d+)?"
PERIOD = r"(?:hour|hr|month|mo|year|yr|annum|week|wk)"

# Two directions: currency-before-number ("$30", "CHF 4'500") and
# number-before-currency ("4500 EUR", "25-30 CHF per hour) — European
# postings frequently use the postfix form, which a currency-prefix-only
# pattern would silently miss entirely.
COMP_PREFIX_RE = re.compile(
    rf"{CURRENCY}\s?{NUM}(?:\s?(?:-|–|to)\s?{CURRENCY}?\s?{NUM})?"
    rf"(?:\s?(?:/|per)\s?{PERIOD})?",
    re.IGNORECASE,
)
COMP_POSTFIX_RE = re.compile(
    rf"{NUM}(?:\s?(?:-|–|to)\s?{NUM})?\s?{CURRENCY}"
    rf"(?:\s?(?:/|per)\s?{PERIOD})?",
    re.IGNORECASE,
)
STIPEND_RE = re.compile(r"stipend[^.\n]{0,80}", re.IGNORECASE)

# A match physically close to one of these words is almost certainly THE
# posting's actual pay, not an unrelated dollar figure elsewhere in the
# text (a referral bonus, a company AUM figure, etc). This is a proximity
# preference, not a value judgement — it never rejects a number for being
# implausible, it just prefers whichever match sits nearest to pay-language
# when there's more than one candidate in the text.
COMP_CONTEXT_RE = re.compile(
    r"(?:salary|compensation|stipend|hourly rate|base pay|total comp|"
    r"pay(?:ment)?|wage|remuneration)",
    re.IGNORECASE,
)

MONTHS = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
)
DATE_TOKEN = (
    rf"(?:{MONTHS}\s+\d{{1,2}},?\s+\d{{4}}"  # "June 15, 2026" / "June 15 2026"
    rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\s+\d{{4}}"  # "15 June 2026" / "15th June 2026"
    rf"|{MONTHS}\s+\d{{4}}"  # "June 2026"
    rf"|\d{{4}}-\d{{2}}-\d{{2}}"  # "2026-06-15"
    rf"|(?:Summer|Fall|Autumn|Winter|Spring)\s+\d{{4}})"  # "Summer 2026"
)

# Explicit context ("start date: June 2026") is tried first, with up to ~20
# characters of filler allowed between the trigger phrase and the date
# itself ("expected to start work in June 2026"). A bare "June 2026"
# anywhere in the text is a much weaker signal — it could be a graduation
# window, a copyright year, a company-founding date — so it's only used as
# a fallback, and even then any candidate whose surrounding context looks
# like one of those false-positive patterns is skipped rather than trusted.
START_TRIGGER = (
    r"(?:start(?:ing)? date|starting|start(?:s)?|commenc\w*|begin\w*|"
    r"anticipated start|target start|expected start|"
    r"program (?:starts|begins)|internship (?:starts|begins)|"
    r"join(?:ing)? (?:us|the team) in)"
)
START_DATE_CONTEXT_RE = re.compile(
    rf"{START_TRIGGER}\W{{0,20}}({DATE_TOKEN})",
    re.IGNORECASE,
)
START_DATE_BARE_RE = re.compile(rf"\b({DATE_TOKEN})\b", re.IGNORECASE)
START_DATE_EXCLUDE_RE = re.compile(
    r"graduat\w*|degree|class of|founded|since \d{4}|copyright|©|"
    r"complet\w*\s+(?:your|their|his|her)|obtain\w*",
    re.IGNORECASE,
)

# Word-form numbers ("three-month internship") are common enough phrasing
# that a digits-only pattern would systematically miss them.
WORD_NUMS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
}
NUM_TOKEN = rf"(?:\d{{1,2}}|{'|'.join(WORD_NUMS)})"
DURATION_RE = re.compile(
    # Hyphen-joined units ("12-week", "6-month") have no space between the
    # number and the unit at all, so that separator has to be optional,
    # not just the space-or-nothing a plain \s? would allow.
    rf"\b({NUM_TOKEN})(?:[\s-]?(?:-|–|to)[\s-]?({NUM_TOKEN}))?[\s-]?(month|months|week|weeks)\b",
    re.IGNORECASE,
)

LOAD_RE = re.compile(r"\b(full[- ]?time|part[- ]?time)\b", re.IGNORECASE)


def strip_html(text):
    if not text:
        return ""
    # Some sources (Greenhouse) double-escape: the "content" field contains
    # literal "&lt;p&gt;" text rather than real "<p>" tags, so tag-stripping
    # has to happen after unescaping, and a second unescape pass mops up any
    # entities that were themselves nested inside that escaped markup.
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_compensation(text):
    candidates = list(COMP_PREFIX_RE.finditer(text)) + list(COMP_POSTFIX_RE.finditer(text))
    if candidates:
        # Prefer whichever match sits closest to actual pay-language, e.g.
        # "Base Salary: $200,000" over some unrelated figure mentioned
        # earlier in the text — proximity preference only, never a
        # judgement about whether the number itself looks right.
        def distance_to_context(m):
            window_start = max(0, m.start() - 40)
            window = text[window_start:m.end() + 10]
            ctx = COMP_CONTEXT_RE.search(window)
            return abs(m.start() - (window_start + ctx.start())) if ctx else 10_000

        best = min(candidates, key=distance_to_context)
        return best.group(0).strip()

    m = STIPEND_RE.search(text)
    if m:
        return m.group(0).strip()
    return None


def extract_start_date(text):
    m = START_DATE_CONTEXT_RE.search(text)
    if m:
        return m.group(1)

    # Range phrasing ("graduating between December 2027 and August 2028")
    # poisons BOTH dates, not just the first — once one date in a sentence
    # is excluded, keep excluding forward for a bit so the second half of
    # the same "X and Y" construct doesn't slip through on its own.
    excluded_until = -1
    for m in START_DATE_BARE_RE.finditer(text):
        window_start = max(0, m.start() - 40)
        preceding = text[window_start:m.start()]
        if START_DATE_EXCLUDE_RE.search(preceding) or m.start() < excluded_until:
            excluded_until = m.end() + 40
            continue
        return m.group(1)
    return None


def extract_duration(text):
    m = DURATION_RE.search(text)
    if not m:
        return None
    lo, hi, unit = m.groups()
    lo = WORD_NUMS.get(lo.lower(), lo)
    if hi:
        hi = WORD_NUMS.get(hi.lower(), hi)
        return f"{lo}-{hi} {unit}"
    return f"{lo} {unit}"


def extract_load(text):
    m = LOAD_RE.search(text)
    if not m:
        return None
    return "Full-time" if "full" in m.group(1).lower() else "Part-time"


def format_posted_at(value):
    """Normalize the wildly different `posted_at` formats each connector
    returns: Greenhouse/Ashby/SmartRecruiters give ISO datetimes, Lever
    gives epoch milliseconds, Workday already gives a relative string like
    "Posted Today", Workable gives a bare ISO date, Bain gives nothing."""
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)):
        try:
            seconds = value / 1000 if value > 10_000_000_000 else value
            return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%d %b %Y")
        except (ValueError, OSError, OverflowError):
            return str(value)

    text = str(value)
    if re.search(r"\b(posted|ago|today|yesterday)\b", text, re.IGNORECASE):
        return text  # Workday-style relative string — already human-readable

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%d %b %Y")
    except ValueError:
        return text


def normalize_load(value):
    if not value:
        return None
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)  # "FullTime" -> "Full Time"
    value = value.strip().lower().replace(" ", "-")
    if "full" in value:
        return "Full-time"
    if "part" in value:
        return "Part-time"
    return value.replace("-", " ").title()


def enrich_fields(job):
    """Fill compensation/start_date/duration/load onto `job`, preferring any
    structured values a connector already set (job["_compensation"], etc.)
    over regex matches against job["_description"]."""
    text = strip_html(job.get("_description"))

    job["compensation"] = job.get("_compensation") or extract_compensation(text) or NOT_LISTED
    job["start_date"] = job.get("_start_date") or extract_start_date(text) or NOT_LISTED
    job["duration"] = job.get("_duration") or extract_duration(text) or NOT_LISTED
    job["load"] = normalize_load(job.get("_load")) or extract_load(text) or NOT_LISTED
    job["posted"] = format_posted_at(job.get("posted_at")) or NOT_LISTED
    return job

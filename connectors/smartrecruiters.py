import requests

HEADERS = {"User-Agent": "job-alerts-bot/1.0 (personal internship tracker)"}

PAGE_SIZE = 100
MAX_OFFSET = 500


def fetch(company_cfg):
    token = company_cfg["token"]
    url = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"

    jobs = []
    offset = 0
    while offset < MAX_OFFSET:
        resp = requests.get(
            url, params={"limit": PAGE_SIZE, "offset": offset}, headers=HEADERS, timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("content", [])
        if not content:
            break

        for j in content:
            loc = j.get("location") or {}
            location = ", ".join(filter(None, [loc.get("city"), loc.get("country")])) or None
            jobs.append({
                "id": f"smartrecruiters:{token}:{j['id']}",
                "company": company_cfg["company"],
                "title": j.get("name"),
                "location": location,
                "url": f"https://jobs.smartrecruiters.com/{token}/{j['id']}",
                "posted_at": j.get("releasedDate"),
                # Compensation/full description live behind the per-posting
                "_detail_url": j.get("ref"),
            })

        offset += PAGE_SIZE
        if offset >= data.get("totalFound", 0):
            break

    return jobs


def _format_compensation(comp):
    if not comp:
        return None
    lo, hi = comp.get("min"), comp.get("max")
    currency = comp.get("currency", "")
    period = (comp.get("period") or "").lower()
    if lo is None or hi is None:
        return None
    return f"{currency} {lo:,}–{hi:,} / {period}" if period else f"{currency} {lo:,}–{hi:,}"


def enrich(job):
    """Fetch full posting detail — this is where compensation actually
    lives (as a structured field!) plus the full description text. Only
    call this on postings that already passed filtering and dedup."""
    resp = requests.get(job["_detail_url"], headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    job["_compensation"] = _format_compensation(data.get("compensation"))
    job["_load"] = (data.get("typeOfEmployment") or {}).get("label")

    sections = (data.get("jobAd") or {}).get("sections") or {}
    text_parts = [
        sections.get(key, {}).get("text", "")
        for key in ("jobDescription", "qualifications", "additionalInformation")
    ]
    job["_description"] = " ".join(part for part in text_parts if part)

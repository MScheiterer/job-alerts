import requests

HEADERS = {
    "User-Agent": "job-alerts-bot/1.0 (personal internship tracker)",
    "Content-Type": "application/json",
}

PAGE_SIZE = 20
MAX_OFFSET = 100  # server-side keyword search should surface matches well before this


def fetch(company_cfg):
    tenant = company_cfg["tenant"]
    wd = company_cfg["wd"]
    site = company_cfg["site"]
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    url = f"{base}/wday/cxs/{tenant}/{site}/jobs"

    jobs = []
    seen_paths = set()

    # Workday's searchText does full-text matching server-side, so we don't
    # need to paginate through every posting — just the ones near these terms.
    for query in ("intern", "internship"):
        offset = 0
        while offset < MAX_OFFSET:
            payload = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": query}
            resp = requests.post(url, json=payload, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            postings = data.get("jobPostings", [])
            if not postings:
                break

            for p in postings:
                path = p.get("externalPath")
                if not path or path in seen_paths:
                    continue
                seen_paths.add(path)
                # Some Workday tenants (e.g. Accenture) leave locationsText
                # empty in the list response; bulletFields' second entry is
                # often a human-readable location as a fallback. enrich()
                # overwrites this with the authoritative value from the
                # detail call for anything that survives filtering.
                bullets = p.get("bulletFields") or []
                fallback_location = bullets[1] if len(bullets) > 1 else None
                jobs.append({
                    "id": f"workday:{tenant}:{site}:{path}",
                    "company": company_cfg["company"],
                    "title": p.get("title"),
                    "location": p.get("locationsText") or fallback_location,
                    "url": f"{base}/{site}{path}",
                    "posted_at": p.get("postedOn"),
                    # Full description/timeType need a per-job detail call —
                    # only worth making for postings that survive filtering
                    # and dedup, so just stash the URL here (see enrich()).
                    "_detail_url": f"{base}/wday/cxs/{tenant}/{site}{path}",
                })

            offset += PAGE_SIZE
            if offset >= data.get("total", 0):
                break

    return jobs


def enrich(job):
    """Fetch full description + workload for a single posting. Only call
    this on postings that already passed filtering and dedup — Workday
    doesn't include this in the list response, so it costs one extra
    request per job."""
    resp = requests.get(job["_detail_url"], headers=HEADERS, timeout=20)
    resp.raise_for_status()
    info = resp.json().get("jobPostingInfo", {})
    job["_description"] = info.get("jobDescription")
    job["_load"] = info.get("timeType")
    # The detail call's location is authoritative and fills in cases where
    # the list response left locationsText empty (see fetch()).
    location = info.get("location")
    additional = info.get("additionalLocations") or []
    if location:
        job["location"] = ", ".join([location, *additional]) if additional else location
    # Note: Workday's "startDate" field reflects when the requisition was
    # posted, not the internship's employment start date — deliberately not
    # used here; start date comes from regex-scanning the description.

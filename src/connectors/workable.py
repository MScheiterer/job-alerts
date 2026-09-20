import requests

HEADERS = {"User-Agent": "job-alerts-bot/1.0 (personal internship tracker)"}


def fetch(company_cfg):
    token = company_cfg["token"]
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for j in data.get("jobs", []):
        location = ", ".join(filter(None, [j.get("city"), j.get("country")])) or None
        jobs.append({
            "id": f"workable:{token}:{j['shortcode']}",
            "company": company_cfg["company"],
            "title": j.get("title"),
            "location": location,
            "url": j.get("url") or j.get("shortlink"),
            "posted_at": j.get("published_on"),
            # The widget API doesn't expose a full description, so
            # compensation/start date/duration stay "not listed" for these.
            "_load": j.get("employment_type"),
        })
    return jobs

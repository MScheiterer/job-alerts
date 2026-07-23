import requests

HEADERS = {"User-Agent": "job-alerts-bot/1.0 (personal internship tracker)"}


def fetch(company_cfg):
    token = company_cfg["token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    # content=true returns full HTML description inline for every job in one
    # call — no need for a per-job detail fetch.
    resp = requests.get(url, params={"content": "true"}, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "id": f"greenhouse:{token}:{j['id']}",
            "company": company_cfg["company"],
            "title": j.get("title"),
            "location": (j.get("location") or {}).get("name"),
            "url": j.get("absolute_url"),
            "posted_at": j.get("first_published") or j.get("updated_at"),
            "_description": j.get("content"),
        })
    return jobs

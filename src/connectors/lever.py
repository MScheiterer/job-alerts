import requests

HEADERS = {"User-Agent": "job-alerts-bot/1.0 (personal internship tracker)"}


def fetch(company_cfg):
    token = company_cfg["token"]
    url = f"https://api.lever.co/v0/postings/{token}"
    resp = requests.get(url, params={"mode": "json"}, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for j in data:
        jobs.append({
            "id": f"lever:{token}:{j['id']}",
            "company": company_cfg["company"],
            "title": j.get("text"),
            "location": (j.get("categories") or {}).get("location"),
            "url": j.get("hostedUrl"),
            "posted_at": j.get("createdAt"),
            "_description": j.get("descriptionPlain"),
            "_load": (j.get("categories") or {}).get("commitment"),
        })
    return jobs

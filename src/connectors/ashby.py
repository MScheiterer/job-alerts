import requests

HEADERS = {"User-Agent": "job-alerts-bot/1.0 (personal internship tracker)"}


def fetch(company_cfg):
    token = company_cfg["token"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "id": f"ashby:{token}:{j['id']}",
            "company": company_cfg["company"],
            "title": j.get("title"),
            "location": j.get("location"),
            "url": j.get("jobUrl"),
            "posted_at": j.get("publishedAt"),
            "_description": j.get("descriptionPlain"),
            "_load": j.get("employmentType"),
        })
    return jobs

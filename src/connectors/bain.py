import requests

# Bain has no third-party ATS — this is a one-off connector for their own
# first-party careers-site API.
URL = "https://www.bain.com/en/api/jobsearch/keyword/get"
HEADERS = {
    "User-Agent": "job-alerts-bot/1.0 (personal internship tracker)",
    "Referer": "https://www.bain.com/careers/find-a-role/",
}


def fetch(company_cfg):
    jobs = []
    seen_ids = set()

    for query in ("intern", "internship"):
        resp = requests.get(URL, params={"keyword": query}, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        for j in data.get("results", []):
            job_id = j.get("JobId")
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            locations = j.get("Location") or []
            location = ", ".join(loc.strip() for loc in locations[:3]) or None

            jobs.append({
                "id": f"bain:{job_id}",
                "company": company_cfg["company"],
                "title": j.get("JobTitle"),
                "location": location,
                "url": "https://www.bain.com" + (j.get("Link") or ""),
                "posted_at": None,
                "_description": j.get("JobDescription"),
                "_load": j.get("EmployeeType"),
            })

    return jobs

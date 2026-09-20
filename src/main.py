import argparse
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from connectors import ashby, bain, greenhouse, lever, smartrecruiters, workable, workday
from extract import enrich_fields
from filters import filter_jobs, load_filters
from notifier import send_email
from store import filter_new, init_db, mark_seen

load_dotenv()

CONNECTORS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "workday": workday.fetch,
    "smartrecruiters": smartrecruiters.fetch,
    "workable": workable.fetch,
    "bain": bain.fetch,
}

# Connectors whose list responses don't include a full description/workload —
# these need one extra request per posting, so only ever called on postings
# that already survived filtering and dedup, never on the full fetch.
ENRICHERS = {
    "workday": workday.enrich,
    "smartrecruiters": smartrecruiters.enrich,
}

COMPANIES_PATH = Path(__file__).parent / "companies.yaml"


def load_companies():
    with open(COMPANIES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run(seed=False):
    companies = load_companies()
    filters_cfg = load_filters()
    conn = init_db()

    all_jobs = []
    for entry in companies:
        if not entry.get("enabled", True):
            continue
        fetch = CONNECTORS.get(entry["connector"])
        if fetch is None:
            print(f"[skip] unknown connector '{entry['connector']}' for {entry['company']}")
            continue
        try:
            jobs = fetch(entry)
        except Exception as e:
            print(f"[error] {entry['company']}: {e}")
            continue
        for j in jobs:
            j["_connector"] = entry["connector"]
        print(f"[ok] {entry['company']}: {len(jobs)} postings fetched")
        all_jobs.extend(jobs)
        time.sleep(0.5)  # be polite between companies

    matched = filter_jobs(all_jobs, filters_cfg)
    print(f"\n{len(matched)} postings match filters (of {len(all_jobs)} fetched total)")

    if seed:
        mark_seen(conn, matched)
        print(f"[seed] marked {len(matched)} currently-open matches as seen — no email sent")
        conn.close()
        return

    new_jobs = filter_new(conn, matched)
    print(f"{len(new_jobs)} are new since the last run")

    if new_jobs:
        for j in new_jobs:
            enricher = ENRICHERS.get(j["_connector"])
            if enricher:
                try:
                    enricher(j)
                except Exception as e:
                    print(f"  [enrich-error] {j['company']} / {j['title']}: {e}")
            enrich_fields(j)
            print(
                f"  NEW: [{j['company']}] {j['title']} — {j.get('location')} "
                f"| posted {j['posted']} | {j['compensation']} | starts {j['start_date']} "
                f"| {j['duration']} | {j['load']}"
            )
        send_email(new_jobs)
        mark_seen(conn, new_jobs)
        print("Email sent.")
    else:
        print("Nothing new — no email sent.")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll company career pages for new internship postings.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Mark all currently matching postings as seen without emailing. "
        "Run this once on first setup so you don't get flooded with every "
        "already-open posting on your very first run.",
    )
    args = parser.parse_args()
    run(seed=args.seed)

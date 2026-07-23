# job-alerts

Polls internship postings straight from company career-page APIs (Greenhouse,
Lever, Ashby, Workday, SmartRecruiters, Workable, plus a one-off Bain
connector) and emails you when something new matches your criteria.

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in SMTP credentials.
   - For Gmail: enable 2FA, then create an
     [app password](https://myaccount.google.com/apppasswords) and use that
     as `SMTP_PASS` — not your normal password.
3. First run — bootstraps the seen-jobs database so you don't get emailed
   every currently-open posting at once:
   ```
   python main.py --seed
   ```
4. Normal runs — only genuinely new postings trigger an email:
   ```
   python main.py
   ```

## Scheduling

- **Local (now)**: Windows Task Scheduler → run `python main.py` every few
  hours.
- **GitHub Actions (later)**: once this is in a repo, commit `seen_jobs.db`
  back after each run so dedup state persists between runs. Not set up yet.

## Tuning

- `companies.yaml` — add or remove companies. Two entries (`ASML`, `Hudson
  River Trading`) ship with `enabled: false` because their platform is known
  but the exact endpoint/token couldn't be confirmed — flip to `true` once
  you've found it via browser devtools (Network tab → filter XHR/Fetch →
  search a role → look for the JSON response).
- `filters.yaml` — internship keywords, target-role keywords, exclude terms,
  and the EU/UK/US location allow-list.

## Coverage

33 companies wired up here, all with confirmed public JSON APIs — no HTML
scraping or browser automation. That's the companies from the reconnaissance
report tagged "200 OK" minus the two above. The remaining ~35 companies from
that survey (Google, Apple, Tesla, Meta, McKinsey, most quant funds like
Optiver/Jane Street/Citadel, etc.) have no discoverable API and are out of
scope for this version.

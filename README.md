# job-alerts

Polls company career-page APIs on a schedule and emails a digest of new
internship postings that match a set of role/location filters. Built to
stay ahead of summer 2027 application deadlines for ML/research and
quant/SWE internships without manually re-checking career pages.

## Architecture

- **Connectors** (`src/connectors/`) — one module per ATS platform
  (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, plus a
  one-off Bain connector), each hitting that platform's public JSON API.
  No HTML scraping or browser automation.
- **Filter** (`src/filters.py`) — title/role/location keyword matching
  against `src/filters.yaml`, applied to everything the connectors fetch.
- **Dedup store** (`src/store.py`) — a SQLite table of previously-seen
  job IDs, so only genuinely new postings trigger a notification.
- **Enrichment** (`src/extract.py`, connector `enrich()` functions) —
  fills in compensation/start date/duration/workload, preferring structured
  API fields where a platform exposes them and falling back to regex
  extraction from the posting description. Only run on postings that
  survive filtering and dedup, to minimize extra requests.
- **Notifier** (`src/notifier.py`) — formats and emails matched postings
  via SMTP.
- **Scheduler** (`.github/workflows/job-alerts.yml`) — GitHub Actions runs
  the poller every 3 hours (cron) or on manual dispatch, then commits the
  updated dedup database back to the repo so state persists between runs
  without a separate hosted database.

```
companies.yaml ──► connectors/* ──► filters.py ──► store.py (dedup)
                                                        │
                                                        ▼
                                              extract.py + enrich()
                                                        │
                                                        ▼
                                                  notifier.py ──► email
```

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in SMTP credentials.
   - For Gmail: enable 2FA, then create an
     [app password](https://myaccount.google.com/apppasswords) and use that
     as `SMTP_PASS` — not your normal password.
3. First run — bootstraps the seen-jobs database so you don't get emailed
   every currently-open posting at once:
   ```
   python src/main.py --seed
   ```
4. Normal runs — only genuinely new postings trigger an email:
   ```
   python src/main.py
   ```

### Running on a schedule

The included GitHub Actions workflow (`.github/workflows/job-alerts.yml`)
runs the poller on a cron schedule and needs these repository secrets set
(Settings → Secrets and variables → Actions):

| Secret        | Purpose                          |
|---------------|-----------------------------------|
| `SMTP_HOST`   | e.g. `smtp.gmail.com`             |
| `SMTP_PORT`   | e.g. `587`                        |
| `SMTP_USER`   | sending account                  |
| `SMTP_PASS`   | app password, not account password |
| `ALERT_TO`    | address to receive alerts        |

The workflow needs `permissions: contents: write` (already set) so it can
commit the updated dedup database back to the repo after each run. Adjust
the `cron` expression to change polling frequency.

### Tuning

- `src/companies.yaml` — add or remove companies. Entries with
  `enabled: false` have their platform identified but the exact
  endpoint/token unconfirmed — flip to `true` once you've found it via
  browser devtools (Network tab → filter XHR/Fetch → search a role → look
  for the JSON response).
- `src/filters.yaml` — internship keywords, target-role keywords, exclude
  terms, and the location allow-list.

## Sample output

Each email digest groups matched postings by company:

```
Anthropic
  - Research Engineer Intern (Zurich, Switzerland)
    Posted:       2026-08-14
    Compensation: not listed
    Start date:   Summer 2027
    Duration:     12 weeks
    Load:         Full-time
    https://job-boards.greenhouse.io/anthropic/jobs/xxxxxxx
```

## Limitations / next steps

- Coverage is limited to companies with a confirmed public JSON API; sites
  requiring HTML scraping or browser automation are out of scope by design.
- Compensation/start-date/duration extraction is regex-based text matching
  over free-form descriptions and will miss unusual phrasing when a
  platform doesn't expose the field as structured data.
- Dedup state lives in a SQLite file committed back to the repo by CI —
  simple and needs no external database, but it does mean the commit
  history accumulates an automated commit per run.

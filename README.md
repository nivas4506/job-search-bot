# Job + Hackathon Alerts Automation

This project gives you 2 automations:

1. SDE intern job alerts for top product companies (Microsoft, Google, Amazon, and more)
2. Hackathon alerts for major India events

It runs via search RSS feeds, filters by keywords, deduplicates results, and writes reports.
Optionally, it can email alerts automatically.
Email alerts are sent with a styled HTML layout and a plain-text fallback.
Jobs alerts now use Google search results.
Job links are resolved with a best-effort step to open direct application pages.
When a direct application page cannot be found, alerts explicitly say: "Direct application page not available for this role." and do not include a generic homepage link.

## Project Structure

- `config/jobs_queries.yaml` - Internship job search queries
- `config/hackathons_queries.yaml` - Hackathon search queries
- `src/alerts.py` - Shared engine (fetch, filter, dedupe, notify)
- `src/run_jobs_alerts.py` - Run job alerts flow
- `src/run_hackathon_alerts.py` - Run hackathon alerts flow
- `outputs/` - Markdown reports from each run
- `data/seen_items.db` - Deduplication database

## Setup (Windows)

### 1) Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r requirements.txt
```

### 3) Optional email configuration

Copy `.env.example` to `.env` and fill SMTP values.

For Gmail, use App Password (not your normal password).

## Run Manually

### Job alerts

```powershell
python src/run_jobs_alerts.py
```

### Hackathon alerts

```powershell
python src/run_hackathon_alerts.py
```

Reports are saved into `outputs/`.

## Run With Docker

This project can run in containers using `docker` and `docker compose`.

### 1) Build image

```powershell
docker compose build
```

### 2) Run jobs alerts once

```powershell
docker compose run --rm jobs-alerts
```

### 3) Run hackathon alerts once

```powershell
docker compose run --rm hackathon-alerts
```

Container runs use your local `.env` and persist outputs in `outputs/` and dedupe data in `data/`.

## Customize Queries

Edit:

- `config/jobs_queries.yaml`
- `config/hackathons_queries.yaml`

Each query supports:

- `name`
- `query`
- `include_keywords`
- `include_all_keywords` (all must appear)
- `exclude_keywords`
- `allowed_domains` (restrict to trusted company domains)
- `required_url_keywords` (prefer direct apply/job URLs)

Global config supports:

- `recent_days` (drops older items when publish date is available)

Tips:

- Add more companies in the `query` using `OR`.
- Keep `include_keywords` strict to reduce spam.
- Use `include_all_keywords: [india]` to force India relevance.
- Add `exclude_keywords` like `senior`, `closed`, `ended`.

## Automate with Task Scheduler

Create 2 scheduled tasks.

### Task 1: Jobs (every 6 hours)

Program/script:

```text
C:\Users\A\OneDrive\Documents\Jobs automations\.venv\Scripts\python.exe
```

Arguments:

```text
src/run_jobs_alerts.py
```

Start in:

```text
C:\Users\A\OneDrive\Documents\Jobs automations
```

### Task 2: Hackathons (daily)

Program/script:

```text
C:\Users\A\OneDrive\Documents\Jobs automations\.venv\Scripts\python.exe
```

Arguments:

```text
src/run_hackathon_alerts.py
```

Start in:

```text
C:\Users\A\OneDrive\Documents\Jobs automations
```

## Notes

- First run may include many old links. Later runs only show new links due to dedupe.
- Search RSS can include noisy results. Tune your YAML keywords for better precision.
- If email is not configured, reports are still generated locally.

# Job Search Bot

A practical automation bot for two high-signal streams:

1. SDE internship applications at top product companies
2. Major India-focused hackathons and coding challenges

It discovers opportunities, filters noise, prioritizes direct apply links, enforces India-only mode, and sends formatted email alerts.

## Highlights

- Direct application link prioritization
- India-only filtering support
- Query-based company/event targeting
- Email alerts with structured role details
- Local run, Docker run, and Vercel API support
- Stateful dedupe locally (SQLite) and optional serverless dedupe via Upstash

## Project Layout

- `src/alerts.py` - core pipeline (fetch, filter, dedupe, format, notify)
- `src/run_jobs_alerts.py` - jobs runner
- `src/run_hackathon_alerts.py` - hackathons runner
- `config/jobs_queries.yaml` - jobs query rules
- `config/hackathons_queries.yaml` - hackathon query rules
- `api/jobs.py` - Vercel API endpoint for jobs
- `api/hackathons.py` - Vercel API endpoint for hackathons
- `api/health.py` - Vercel health endpoint
- `vercel.json` - Vercel function config
- `outputs/` - generated markdown reports
- `data/seen_items.db` - local dedupe store

## Quick Start (Local Python)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy environment template:

```powershell
copy .env.example .env
```

Run jobs:

```powershell
python src/run_jobs_alerts.py
```

Run hackathons:

```powershell
python src/run_hackathon_alerts.py
```

## Docker Usage

Build:

```powershell
docker compose build
```

Run jobs once:

```powershell
docker compose run --rm jobs-alerts
```

Run hackathons once:

```powershell
docker compose run --rm hackathon-alerts
```

## Vercel Deployment

Current Vercel endpoints:

- `/api/jobs`
- `/api/hackathons`
- `/api/health`

Useful query params for `/api/jobs` and `/api/hackathons`:

- `max_results=5`
- `format=markdown`

Example:

- `/api/jobs?max_results=5`
- `/api/hackathons?format=markdown`

### Vercel environment variables

Required:

- `EMAIL_ENABLED`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `ALERT_FROM_EMAIL`
- `ALERT_TO_EMAIL`
- `MAX_RESULTS_PER_QUERY`

Optional:

- `CRON_SECRET`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

## Query Configuration

Editable files:

- `config/jobs_queries.yaml`
- `config/hackathons_queries.yaml`

Per-query keys:

- `name`
- `query`
- `include_keywords`
- `include_all_keywords`
- `exclude_keywords`
- `allowed_domains`
- `required_url_keywords`

Global keys:

- `recent_days`
- `direct_job_links`
- `direct_apply_only`
- `india_only`

## Alert Rules in Plain Words

- Only trusted domains are allowed (when configured).
- Only direct application pages are retained in strict mode.
- If direct apply page is not found, message explicitly says so.
- India-only mode drops non-India opportunities.

## Scheduling (Windows)

The repo includes a task-runner script:

- `run_jobs_alerts_docker.bat`

You can schedule it via Task Scheduler (already configured in this workspace as `Job Alerts Every 3 Hours`).

## Notes

- Local dedupe uses SQLite in `data/seen_items.db`.
- Serverless filesystems are ephemeral; use Upstash for persistent dedupe on Vercel.
- Search result quality depends on query quality; tune YAML rules regularly.

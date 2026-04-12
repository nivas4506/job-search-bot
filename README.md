# Job Search Bot

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-API%20Deploy-000000?logo=vercel&logoColor=white)
![Schedule](https://img.shields.io/badge/Schedule-Every%203%20Hours-0F766E)
![Region](https://img.shields.io/badge/Region-India%20Only-F97316)
![Apply%20Links](https://img.shields.io/badge/Links-Direct%20Apply%20Only-7C3AED)

Automated alerts for high-value opportunities, focused on India.

- SDE internship applications at top product companies
- Major hackathons and coding events in India

The bot collects opportunities, filters low-signal results, resolves direct apply links, and delivers structured email alerts.

## Why this is useful

- No homepage spam: direct-apply-first workflow
- India-first filtering for both jobs and hackathons
- Reusable query rules in YAML
- Works locally, in Docker, and on Vercel APIs
- Dedupe support: SQLite locally, Upstash option for serverless

## Core capabilities

| Capability | What it does |
|---|---|
| Jobs discovery | Finds internship roles from trusted company domains |
| Hackathon discovery | Finds relevant India-focused events/challenges |
| Direct apply enforcement | Keeps direct application links in strict mode |
| India-only mode | Drops non-India opportunities |
| Email formatting | Sends readable, structured alert messages |
| Dedupe | Prevents repeat alerts for previously seen items |

## Project map

- [src/alerts.py](src/alerts.py): core pipeline (fetch, filter, dedupe, notify)
- [src/run_jobs_alerts.py](src/run_jobs_alerts.py): jobs runner
- [src/run_hackathon_alerts.py](src/run_hackathon_alerts.py): hackathons runner
- [config/jobs_queries.yaml](config/jobs_queries.yaml): jobs rules
- [config/hackathons_queries.yaml](config/hackathons_queries.yaml): hackathons rules
- [api/jobs.py](api/jobs.py): Vercel jobs endpoint
- [api/hackathons.py](api/hackathons.py): Vercel hackathons endpoint
- [api/health.py](api/health.py): health endpoint
- [vercel.json](vercel.json): Vercel runtime config
- [outputs](outputs): generated reports
- [data/seen_items.db](data/seen_items.db): local dedupe DB

## Local quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
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

## Docker

```powershell
docker compose build
docker compose run --rm jobs-alerts
docker compose run --rm hackathon-alerts
```

## Vercel API mode

Available endpoints:

- `/api/jobs`
- `/api/hackathons`
- `/api/cron`
- `/api/health`

Useful params:

- `max_results=5`
- `format=markdown`

Examples:

- `/api/jobs?max_results=5`
- `/api/hackathons?format=markdown`

## Required environment variables

| Name | Example value |
|---|---|
| `EMAIL_ENABLED` | `true` |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | `your-email@gmail.com` |
| `SMTP_PASSWORD` | `your-app-password` |
| `SMTP_USE_TLS` | `true` |
| `ALERT_FROM_EMAIL` | `your-email@gmail.com` |
| `ALERT_TO_EMAIL` | `recipient@gmail.com` |
| `MAX_RESULTS_PER_QUERY` | `10` |

Optional:

| Name | Example value |
|---|---|
| `CRON_SECRET` | `replace_with_long_random_secret` |
| `UPSTASH_REDIS_REST_URL` | `your Upstash Redis URL` |
| `UPSTASH_REDIS_REST_TOKEN` | `your Upstash Redis token` |

## Query configuration

Edit:

- [config/jobs_queries.yaml](config/jobs_queries.yaml)
- [config/hackathons_queries.yaml](config/hackathons_queries.yaml)

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

## Alert policy

- Trusted domains only when configured
- Direct-apply links only in strict mode
- If direct apply is unavailable: message states it clearly
- India-only mode removes non-India results

## Scheduling (Windows)

Runner script:

- [run_jobs_alerts_docker.bat](run_jobs_alerts_docker.bat)

Task Scheduler can run it every 3 hours (already configured in this workspace as `Job Alerts Every 3 Hours`).

## Scheduling (GitHub Actions)

This repo also includes [.github/workflows/scheduled-alerts.yml](.github/workflows/scheduled-alerts.yml),
which runs both alert pipelines every 3 hours on GitHub Actions.

Required GitHub Actions secrets:

| Name | Example value |
|---|---|
| `EMAIL_ENABLED` | `true` |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | `your-email@gmail.com` |
| `SMTP_PASSWORD` | `your-app-password` |
| `SMTP_USE_TLS` | `true` |
| `ALERT_FROM_EMAIL` | `your-email@gmail.com` |
| `ALERT_TO_EMAIL` | `recipient@gmail.com` |
| `MAX_RESULTS_PER_QUERY` | `10` |

Optional secrets:

| Name | Example value |
|---|---|
| `UPSTASH_REDIS_REST_URL` | `your Upstash Redis URL` |
| `UPSTASH_REDIS_REST_TOKEN` | `your Upstash Redis token` |

Without Upstash, the workflow falls back to a GitHub Actions cache for `data/seen_items.db`.

## Operational notes

- Local dedupe persists in SQLite ([data/seen_items.db](data/seen_items.db))
- Serverless filesystems are ephemeral; use Upstash for persistent dedupe
- Query quality directly impacts alert quality

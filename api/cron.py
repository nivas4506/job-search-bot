from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from vercel import Response

# Make src importable in Vercel serverless runtime.
ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alerts import run_alert_pipeline  # noqa: E402


def handler(request):
    secret = os.getenv("CRON_SECRET", "").strip()
    if secret:
        auth_header = request.headers.get("authorization", "")
        expected = f"Bearer {secret}"
        if auth_header != expected:
            return Response("Unauthorized", status_code=401)

    jobs_new = run_alert_pipeline(config_path="config/jobs_queries.yaml", alert_type="SDE Intern Jobs")
    hacks_new = run_alert_pipeline(config_path="config/hackathons_queries.yaml", alert_type="Hackathons India")

    body = {
        "ok": True,
        "jobs_new": jobs_new,
        "hackathons_new": hacks_new,
    }
    return Response(json.dumps(body), status_code=200, headers={"content-type": "application/json"})

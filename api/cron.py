from http.server import BaseHTTPRequestHandler

from api_common import is_authorized, send_json
from src.alerts import run_alert_pipeline_summary


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not is_authorized(self):
            send_json(self, 401, {"ok": False, "error": "Unauthorized"})
            return

        jobs = run_alert_pipeline_summary(
            config_path="config/jobs_queries.yaml",
            alert_type="SDE Intern Jobs",
        )
        hackathons = run_alert_pipeline_summary(
            config_path="config/hackathons_queries.yaml",
            alert_type="Hackathons India",
        )

        send_json(
            self,
            200,
            {
                "ok": True,
                "message": "Cron run completed",
                "jobs": {
                    "newAfterDedupe": jobs["new_count"],
                    "emailed": jobs["emailed"],
                },
                "hackathons": {
                    "newAfterDedupe": hackathons["new_count"],
                    "emailed": hackathons["emailed"],
                },
            },
        )

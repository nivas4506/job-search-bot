from http.server import BaseHTTPRequestHandler

from api_common import get_max_results, is_authorized, items_to_payload, send_json, send_markdown
from src.alerts import run_alert_pipeline_summary


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not is_authorized(self):
            send_json(self, 401, {"ok": False, "error": "Unauthorized"})
            return

        max_results = get_max_results(self.path)
        summary = run_alert_pipeline_summary(
            config_path="config/hackathons_queries.yaml",
            alert_type="Hackathons India",
            max_results=max_results,
        )

        if "format=markdown" in self.path.lower():
            send_markdown(self, summary["markdown"])
            return

        send_json(
            self,
            200,
            {
                "ok": True,
                "alertType": summary["alert_type"],
                "totalMatched": summary["total_matched"],
                "newAfterDedupe": summary["new_count"],
                "emailed": summary["emailed"],
                "maxResultsPerQuery": max_results,
                "items": items_to_payload(summary["new_items"]),
            },
        )

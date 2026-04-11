from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlparse

from src.alerts import collect_items, load_config, render_markdown


def _items_to_payload(items):
    return [
        {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "published": item.published,
            "summary": item.summary,
            "query_name": item.query_name,
        }
        for item in items
    ]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        try:
            max_results = int(params.get("max_results", [os.getenv("MAX_RESULTS_PER_QUERY", "10")])[0])
        except ValueError:
            max_results = 10

        max_results = max(1, min(max_results, 20))
        config = load_config("config/jobs_queries.yaml")
        items = collect_items(config, max_results)

        if params.get("format", ["json"])[0].lower() == "markdown":
            body = render_markdown("SDE Intern Jobs", items)
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return

        payload = {
            "alertType": "SDE Intern Jobs",
            "stateless": True,
            "count": len(items),
            "maxResultsPerQuery": max_results,
            "items": _items_to_payload(items),
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

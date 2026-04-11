from http.server import BaseHTTPRequestHandler

from api_common import send_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        send_json(
            self,
            200,
            {
                "ok": True,
                "service": "job-search-bot",
                "deploymentMode": "vercel-preview",
                "storage": "tmp-or-upstash",
            },
        )

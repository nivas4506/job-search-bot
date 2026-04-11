import hmac
import json
import os
from urllib.parse import parse_qs, urlparse

from src.alerts import AlertItem


def get_query_params(path: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(path).query)


def get_max_results(path: str) -> int:
    params = get_query_params(path)
    try:
        value = int(params.get("max_results", [os.getenv("MAX_RESULTS_PER_QUERY", "10")])[0])
    except ValueError:
        value = 10
    return max(1, min(value, 20))


def items_to_payload(items: list[AlertItem]) -> list[dict]:
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


def read_header(handler, key: str) -> str:
    return (handler.headers.get(key) or "").strip()


def is_authorized(handler) -> bool:
    secret = os.getenv("CRON_SECRET", "").strip()
    if not secret:
        return True

    params = get_query_params(handler.path)
    auth_header = read_header(handler, "Authorization")
    bearer = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    candidates = [
        bearer,
        read_header(handler, "x-cron-secret"),
        params.get("secret", [""])[0].strip(),
    ]
    return any(hmac.compare_digest(candidate, secret) for candidate in candidates if candidate)


def send_json(handler, status: int, payload: dict) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def send_markdown(handler, body: str) -> None:
    encoded = body.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/markdown; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)

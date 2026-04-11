from __future__ import annotations

import hashlib
from html import escape
import os
import re
import sqlite3
import textwrap
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus, urljoin, urlparse

import feedparser
import requests
import yaml
from dotenv import load_dotenv
import smtplib


BING_RSS_URL = "https://www.bing.com/search"
GOOGLE_SEARCH_URL = "https://www.google.com/search"
JINA_MIRROR_URL = "https://r.jina.ai/http://www.google.com/search"
if os.getenv("VERCEL"):
    DB_PATH = Path("/tmp") / "seen_items.db"
    OUTPUT_DIR = Path("/tmp") / "outputs"
else:
    DB_PATH = Path("data") / "seen_items.db"
    OUTPUT_DIR = Path("outputs")

APPLICATION_PATH_KEYWORDS = (
    "apply",
    "application",
    "job",
    "jobs",
    "position",
    "opening",
    "opportunit",
    "intern",
    "universityinternship",
    "exploremicrosoft",
)

APPLY_ANCHOR_TEXT_KEYWORDS = (
    "apply",
    "apply now",
    "view job",
    "view role",
    "job details",
    "job description",
    "see openings",
    "open positions",
)

INDIA_LOCATION_MARKERS = (
    "india",
    "bangalore",
    "bengaluru",
    "hyderabad",
    "noida",
    "pune",
    "chennai",
    "gurgaon",
    "gurugram",
    "mumbai",
    "delhi",
    "new delhi",
    "kolkata",
    "ahmedabad",
    "coimbatore",
)

NON_INDIA_LOCATION_MARKERS = (
    "united states",
    "usa",
    "u.s.",
    "uk",
    "united kingdom",
    "london",
    "europe",
    "germany",
    "poland",
    "spain",
    "france",
    "singapore",
    "canada",
    "australia",
    "japan",
    "mexico",
)


@dataclass
class AlertItem:
    title: str
    url: str
    source: str
    published: str
    summary: str
    query_name: str

    @property
    def dedupe_key(self) -> str:
        raw = f"{self.title.strip().lower()}|{self.url.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen (
            dedupe_key TEXT PRIMARY KEY,
            first_seen_utc TEXT NOT NULL,
            alert_type TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _upstash_config() -> tuple[str, str] | None:
    url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if not (url and token):
        return None
    return url, token


def _upstash_sadd(set_key: str, value: str) -> bool:
    cfg = _upstash_config()
    if not cfg:
        return False
    base_url, token = cfg
    endpoint = f"{base_url}/sadd/{set_key}/{value}"
    response = requests.post(endpoint, headers={"Authorization": f"Bearer {token}"}, timeout=15)
    response.raise_for_status()
    payload = response.json()
    # Upstash returns 1 when newly inserted, 0 when already present.
    return bool(payload.get("result", 0))


def _only_new_items_upstash(items: list[AlertItem], alert_type: str) -> list[AlertItem]:
    new_items: list[AlertItem] = []
    set_key = f"seen:{alert_type.lower().replace(' ', '_')}"
    for item in items:
        try:
            inserted = _upstash_sadd(set_key, item.dedupe_key)
        except Exception as exc:
            print(f"[WARN] Upstash dedupe failed: {exc}")
            inserted = True
        if inserted:
            new_items.append(item)
    return new_items


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "queries" not in data or not isinstance(data["queries"], list):
        raise ValueError(f"Invalid config in {config_path}: missing 'queries' list")
    return data


def fetch_bing_rss(query: str, timeout: int = 20) -> list[dict]:
    params = {"format": "rss", "q": query, "setlang": "en"}
    response = requests.get(BING_RSS_URL, params=params, timeout=timeout)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    results: list[dict] = []
    for entry in feed.entries:
        results.append(
            {
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", "").strip(),
                "published": entry.get("published", "").strip(),
                "summary": entry.get("summary", "").strip(),
            }
        )
    return results


def fetch_google_html(query: str, timeout: int = 20) -> list[dict]:
    url = f"{JINA_MIRROR_URL}?q={quote_plus(query)}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    content = response.text
    content = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", content)
    results: list[dict] = []
    seen_links: set[str] = set()

    link_pattern = re.compile(r"\[(.*?)\]\((https?://[^\)]+)\)", re.S)

    for match in link_pattern.finditer(content):
        title = match.group(1).strip()
        url = match.group(2).strip()
        if not title or not url.startswith("http") or url in seen_links:
            continue
        seen_links.add(url)

        if title.lower() in {"skip to main content", "accessibility help", "accessibility feedback", "sign in", "all", "jobs", "news", "videos", "images", "forums", "shopping", "short videos", "books", "web", "remote", "no degree", "yesterday", "last 3 days", "last week", "last month", "full time", "part time", "contract", "internship", "any time", "past hour", "past 24 hours", "past week", "past month", "past year", "all results", "verbatim", "choose area", "read more", "ai mode"}:
            continue

        summary = ""
        results.append(
            {
                "title": title,
                "link": url,
                "published": "",
                "summary": summary,
            }
        )
        if len(results) >= 50:
            break

    return results


def keyword_match(text: str, include_keywords: Iterable[str], exclude_keywords: Iterable[str]) -> bool:
    t = text.lower()
    include = [k.lower() for k in include_keywords if k]
    exclude = [k.lower() for k in exclude_keywords if k]

    if include and not any(k in t for k in include):
        return False
    if exclude and any(k in t for k in exclude):
        return False
    return True


def include_all_keywords_match(text: str, include_all_keywords: Iterable[str]) -> bool:
    t = text.lower()
    required = [k.lower() for k in include_all_keywords if k]
    if not required:
        return True
    return all(k in t for k in required)


def domain_matches(url: str, allowed_domains: Iterable[str]) -> bool:
    allowed = [d.lower().strip() for d in allowed_domains if d]
    if not allowed:
        return True

    netloc = urlparse(url).netloc.lower()
    return any(domain in netloc for domain in allowed)


def url_keyword_match(url: str, required_url_keywords: Iterable[str]) -> bool:
    required = [k.lower().strip() for k in required_url_keywords if k]
    if not required:
        return True
    lower_url = url.lower()
    return any(k in lower_url for k in required)


def clean_url(url: str) -> str:
    return url.split("#", 1)[0].strip()


def is_india_based_role(text: str, url: str) -> bool:
    blob = f"{text}\n{url}".lower()
    for marker in INDIA_LOCATION_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", blob):
            return True
    for marker in NON_INDIA_LOCATION_MARKERS:
        if re.search(rf"\b{re.escape(marker)}\b", blob):
            return False
    return False


def is_probable_application_url(url: str, title: str = "") -> bool:
    blob = f"{url}\n{title}".lower()
    return any(k in blob for k in APPLICATION_PATH_KEYWORDS)


def resolve_direct_application_url(url: str, title: str) -> tuple[str, bool]:
    url = clean_url(url)
    if is_probable_application_url(url, title):
        return url, True

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        response.raise_for_status()
    except Exception:
        return url, False

    final_url = clean_url(response.url)
    if is_probable_application_url(final_url, title):
        return final_url, True

    anchor_pattern = re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', response.text, re.I | re.S)
    best_candidate = ""
    best_score = -1
    for match in anchor_pattern:
        href = match.group(1).strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        candidate = clean_url(urljoin(final_url, href))
        if not candidate.startswith("http"):
            continue
        anchor_text = re.sub(r"<[^>]+>", " ", match.group(2)).strip().lower()
        score = 0
        if any(k in anchor_text for k in APPLY_ANCHOR_TEXT_KEYWORDS):
            score += 2
        if is_probable_application_url(candidate, title):
            score += 2
        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_candidate and best_score > 0:
        return best_candidate, True

    return final_url, False


def is_recent_enough(published_text: str, max_age_days: int | None) -> bool:
    if not max_age_days:
        return True
    if not published_text:
        return True

    try:
        published_dt = parsedate_to_datetime(published_text)
        if published_dt.tzinfo is None:
            published_dt = published_dt.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        return published_dt >= now_utc - timedelta(days=max_age_days)
    except Exception:
        # Keep items if date parsing fails so good links are not dropped.
        return True


def collect_items(config: dict, max_results_per_query: int) -> list[AlertItem]:
    items: list[AlertItem] = []
    recent_days = config.get("recent_days")
    search_engine = str(config.get("search_engine", "bing_rss")).strip().lower()
    direct_job_links = bool(config.get("direct_job_links", True))
    direct_apply_only = bool(config.get("direct_apply_only", False))
    india_only = bool(config.get("india_only", False))
    resolved_url_cache: dict[str, tuple[str, bool]] = {}
    if recent_days is not None:
        try:
            recent_days = int(recent_days)
        except Exception:
            recent_days = None

    for q in config["queries"]:
        name = q.get("name", "Unnamed query")
        query = q.get("query", "")
        include_keywords = q.get("include_keywords", [])
        include_all_keywords = q.get("include_all_keywords", [])
        exclude_keywords = q.get("exclude_keywords", [])
        allowed_domains = q.get("allowed_domains", [])
        required_url_keywords = q.get("required_url_keywords", [])

        if not query:
            continue

        try:
            if search_engine in {"google", "google_html"}:
                rows = fetch_google_html(query)
                source = "google_html"
            else:
                rows = fetch_bing_rss(query)
                source = "bing_rss"
        except Exception as exc:
            print(f"[WARN] Query failed: {name} -> {exc}")
            continue

        for row in rows[:max_results_per_query]:
            title = row.get("title", "")
            summary = row.get("summary", "")
            text = f"{title}\n{summary}"
            if not keyword_match(text, include_keywords, exclude_keywords):
                continue
            if not include_all_keywords_match(text, include_all_keywords):
                continue
            if india_only and not is_india_based_role(text, row.get("link", "")):
                continue
            if not is_recent_enough(row.get("published", ""), recent_days):
                continue
            link = row.get("link", "")
            if not link:
                continue
            if not domain_matches(link, allowed_domains):
                continue
            if direct_job_links:
                original_link = link
                if original_link in resolved_url_cache:
                    link, is_apply_page = resolved_url_cache[original_link]
                else:
                    link, is_apply_page = resolve_direct_application_url(original_link, title=title)
                    resolved_url_cache[original_link] = (link, is_apply_page)
                if direct_apply_only and not is_apply_page:
                    items.append(
                        AlertItem(
                            title=title,
                            url="",
                            source=source,
                            published=row.get("published", ""),
                            summary="Direct application page not available for this role.",
                            query_name=name,
                        )
                    )
                    continue
            elif direct_apply_only and not is_probable_application_url(link, title):
                items.append(
                    AlertItem(
                        title=title,
                        url="",
                        source=source,
                        published=row.get("published", ""),
                        summary="Direct application page not available for this role.",
                        query_name=name,
                    )
                )
                continue
            if not url_keyword_match(link, required_url_keywords):
                continue
            if india_only and not is_india_based_role(text, link):
                continue
            items.append(
                AlertItem(
                    title=title,
                    url=link,
                    source=source,
                    published=row.get("published", ""),
                    summary=summary,
                    query_name=name,
                )
            )
    return items


def only_new_items(items: list[AlertItem], alert_type: str) -> list[AlertItem]:
    if _upstash_config():
        return _only_new_items_upstash(items, alert_type)

    ensure_dirs()
    now_utc = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    conn = _db_conn()
    try:
        cur = conn.cursor()
        new_items: list[AlertItem] = []
        for item in items:
            key = item.dedupe_key
            cur.execute("SELECT 1 FROM seen WHERE dedupe_key = ?", (key,))
            exists = cur.fetchone() is not None
            if exists:
                continue
            cur.execute(
                "INSERT INTO seen (dedupe_key, first_seen_utc, alert_type) VALUES (?, ?, ?)",
                (key, now_utc, alert_type),
            )
            new_items.append(item)
        conn.commit()
        return new_items
    finally:
        conn.close()


def render_markdown(alert_type: str, items: list[AlertItem]) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# {alert_type} Alerts ({ts})", ""]
    if not items:
        lines.append("No new matches.")
        return "\n".join(lines)

    for i, item in enumerate(items, start=1):
        summary = textwrap.shorten(item.summary.replace("\n", " "), width=180, placeholder="...")
        url_text = item.url if item.url else "Direct application page not available for this role."
        lines.extend(
            [
                f"## {i}. {item.title}",
                f"- Query: {item.query_name}",
                f"- Published: {item.published or 'N/A'}",
                f"- URL: {url_text}",
                f"- Summary: {summary or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines)


def write_report(alert_type: str, markdown_text: str) -> Path:
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{alert_type.lower().replace(' ', '_')}_{stamp}.md"
    out_path = OUTPUT_DIR / filename
    out_path.write_text(markdown_text, encoding="utf-8")
    return out_path


def render_email_html(alert_type: str, items: list[AlertItem]) -> str:
    def infer_location(item: AlertItem) -> str:
        blob = f"{item.title} {item.summary} {item.url}".lower()

        if "remote" in blob:
            return "Remote"
        if "hybrid" in blob:
            return "Hybrid"

        city_map = {
            "bangalore": "Bangalore",
            "bengaluru": "Bangalore",
            "hyderabad": "Hyderabad",
            "noida": "Noida",
            "pune": "Pune",
            "chennai": "Chennai",
            "gurgaon": "Gurgaon",
            "gurugram": "Gurgaon",
            "mumbai": "Mumbai",
            "delhi": "Delhi",
            "new delhi": "Delhi",
            "kolkata": "Kolkata",
            "ahmedabad": "Ahmedabad",
            "coimbatore": "Coimbatore",
        }

        found: list[str] = []
        for key, label in city_map.items():
            if re.search(rf"\\b{re.escape(key)}\\b", blob) and label not in found:
                found.append(label)

        if found:
            if "india" in blob:
                return f"{', '.join(found[:3])}, India"
            return ", ".join(found[:3])

        if "india" in blob:
            return "India"
        return "Not specified"

    def infer_job_type(item: AlertItem) -> str:
        blob = f"{item.title} {item.summary}".lower()
        if "intern" in blob:
            return "Internship"
        if "contract" in blob:
            return "Contract"
        if "full-time" in blob or "full time" in blob:
            return "Full-Time"
        return "Not specified"

    blocks: list[str] = []
    for item in items[:6]:
        summary = textwrap.shorten(item.summary.replace("\n", " "), width=180, placeholder="...")
        company = item.query_name.split(" Intern", 1)[0].strip()
        location = infer_location(item)
        job_type = infer_job_type(item)
        deadline = "Not specified"

        if item.url:
            apply_section = f"<div class='apply'><strong>Apply Here:</strong><br><a href='{escape(item.url)}' target='_blank' rel='noreferrer'>{escape(item.url)}</a></div>"
        else:
            apply_section = "<div class='apply no-link'><strong>Direct application page not available for this role.</strong></div>"

        blocks.append(
            f"""
            <div class='opp'>
                <p>Hello,</p>
                <p>We've found a new opportunity that matches your profile. Please review the details below and apply using the direct link.</p>
                <hr>
                <p><strong>Role:</strong> {escape(item.title)}</p>
                <p><strong>Company:</strong> {escape(company)}</p>
                <p><strong>Location:</strong> {escape(location)}</p>
                <p><strong>Type:</strong> {escape(job_type)}</p>
                <p><strong>Deadline:</strong> {escape(deadline)}</p>
                <hr>
                <p><strong>Why this opportunity?</strong></p>
                <ul>
                    <li>Matches your software/intern profile and current alert preferences.</li>
                    <li>Relevant skills: coding, problem solving, and developer fundamentals.</li>
                    <li>Growth potential through product engineering exposure.</li>
                </ul>
                {apply_section}
                <hr>
                <p><strong>Quick Tips Before Applying</strong></p>
                <ul>
                    <li>Update your resume</li>
                    <li>Highlight relevant skills</li>
                    <li>Tailor your application to the role</li>
                </ul>
                <p>Best of luck with your application!</p>
                <p>Regards,<br>Job Alerts Bot</p>
            </div>
            """.strip()
        )

    body = "<div class='empty'>No new matches in this run.</div>" if not blocks else "<hr class='sep'>".join(blocks)
    return f"""
    <html>
        <head>
            <style>
                body {{ margin: 0; padding: 0; background: #f7fafc; font-family: Arial, Helvetica, sans-serif; color: #1f2937; }}
                .wrap {{ max-width: 760px; margin: 0 auto; padding: 20px; }}
                .opp {{ background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; margin-bottom: 14px; }}
                p {{ margin: 8px 0; line-height: 1.45; }}
                ul {{ margin: 8px 0 10px 18px; }}
                li {{ margin: 4px 0; }}
                hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 12px 0; }}
                .apply a {{ color: #2563eb; font-weight: 700; word-break: break-all; }}
                .no-link {{ color: #b91c1c; }}
                .sep {{ margin: 20px 0; }}
                .empty {{ background: #fff; border: 1px dashed #cbd5e1; border-radius: 12px; padding: 18px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class=\"wrap\">{body}</div>
        </body>
    </html>
    """.strip()


def send_email_if_configured(subject: str, markdown_text: str, alert_type: str, items: list[AlertItem]) -> bool:
    enabled = os.getenv("EMAIL_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
    if not enabled:
        return False

    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("ALERT_FROM_EMAIL", "").strip()
    to_email_raw = os.getenv("ALERT_TO_EMAIL", "").strip()

    if not (host and username and password and from_email and to_email_raw):
        return False

    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes"}
    recipients = [x.strip() for x in to_email_raw.split(",") if x.strip()]
    if not recipients:
        return False

    plain_msg = MIMEText(markdown_text, "plain", "utf-8")
    html_msg = MIMEText(render_email_html(alert_type, items), "html", "utf-8")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(recipients)
    msg.attach(plain_msg)
    msg.attach(html_msg)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
            server.sendmail(from_email, recipients, msg.as_string())
        return True
    except Exception as exc:
        print(f"[WARN] Email send failed: {exc}")
        return False


def run_alert_pipeline(config_path: str, alert_type: str) -> int:
    load_dotenv()
    max_results = int(os.getenv("MAX_RESULTS_PER_QUERY", "20"))

    config = load_config(config_path)
    items = collect_items(config, max_results)

    unique = {item.dedupe_key: item for item in items}
    deduped_items = list(unique.values())

    new_items = only_new_items(deduped_items, alert_type=alert_type)
    md = render_markdown(alert_type, new_items)
    report_path = write_report(alert_type, md)

    emailed = send_email_if_configured(
        subject=f"{alert_type}: {len(new_items)} new matches",
        markdown_text=md,
        alert_type=alert_type,
        items=new_items,
    )

    print(f"[{alert_type}] Total matched this run: {len(deduped_items)}")
    print(f"[{alert_type}] New after dedupe: {len(new_items)}")
    print(f"[{alert_type}] Report saved: {report_path}")
    print(f"[{alert_type}] Email sent: {emailed}")

    return len(new_items)

"""Collect attributed news links and publish a static, searchable briefing."""

from __future__ import annotations

import argparse
import html
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

API = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "MarketSignalMonitor/1.0 (news-link aggregator)"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read(5_000_000)


def canonical_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not k.lower().startswith("utm_")]
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", urllib.parse.urlencode(query), ""))


def utc_date(value: str) -> str:
    if not value:
        return ""
    for fmt in ("%Y%m%dT%H%M%SZ", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, TypeError):
        pass
    return ""


def gdelt_url(query: str, lookback: str, limit: int) -> str:
    return API + "?" + urllib.parse.urlencode({"query": query, "mode": "artlist", "format": "json", "sort": "datedesc", "timespan": lookback, "maxrecords": limit})


def parse_gdelt(payload: bytes, category: str) -> list[dict]:
    data = json.loads(payload)
    articles = data.get("articles", [])
    if not isinstance(articles, list):
        raise ValueError("GDELT returned an unexpected article list")
    output = []
    for item in articles:
        url = canonical_url(str(item.get("url", "")))
        title = str(item.get("title", "")).strip()
        if url and title:
            output.append({"title": title, "url": url, "source": str(item.get("domain") or urllib.parse.urlsplit(url).netloc), "published": utc_date(str(item.get("seendate", ""))), "category": category})
    return output


def parse_rss(payload: bytes, name: str, category: str) -> list[dict]:
    root = ET.fromstring(payload)
    output = []
    for item in root.findall(".//item"):
        url = canonical_url(item.findtext("link", ""))
        title = (item.findtext("title", "") or "").strip()
        if url and title:
            output.append({"title": title, "url": url, "source": name, "published": utc_date(item.findtext("pubDate", "")), "category": category})
    return output


def merge(existing: list[dict], incoming: list[dict], cap: int) -> list[dict]:
    by_url = {}
    for item in existing + incoming:
        url = canonical_url(str(item.get("url", "")))
        if url and item.get("title"):
            item = dict(item)
            item["url"] = url
            if url not in by_url or item.get("published", "") > by_url[url].get("published", ""):
                by_url[url] = item
    return sorted(by_url.values(), key=lambda x: x.get("published", ""), reverse=True)[:cap]


def render(items: list[dict], updated: str, errors: list[str], categories: list[str]) -> str:
    e = lambda value: html.escape(str(value), quote=True)
    buttons = "".join(f'<button type="button" data-filter="{e(c)}">{e(c)}</button>' for c in categories)
    cards = "".join(
        f'<article class="card" data-category="{e(x["category"])}" data-search="{e(x["title"] + " " + x["source"])}">'
        f'<div class="meta"><span class="tag">{e(x["category"])}</span><span>{e(x["source"])}</span><time>{e(x.get("published", "")[:16].replace("T", " "))} UTC</time></div>'
        f'<h2><a href="{e(x["url"])}" target="_blank" rel="noopener noreferrer">{e(x["title"])}</a></h2></article>'
        for x in items
    )
    warning = f'<p class="warning">Some sources could not be refreshed: {e("; ".join(errors))}</p>' if errors else ""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Market Signal Monitor</title><style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; background:#f5f7fb; color:#16243c }}
* {{ box-sizing:border-box }} body {{ margin:0 }} header {{ background:#10233f; color:white; padding:3rem max(1rem,calc((100vw - 1040px)/2)) 2rem }}
header h1 {{ font-size:clamp(2rem,5vw,3.4rem); letter-spacing:-.04em; margin:.2rem 0 }} header p {{ color:#c5d3e7; max-width:65ch }}
main {{ max-width:1040px; margin:auto; padding:1.5rem 1rem 4rem }} .toolbar {{ display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin-bottom:1rem }}
button,input {{ font:inherit; border:1px solid #cbd5e1; border-radius:.5rem; padding:.65rem .9rem; background:white }} button {{ cursor:pointer }} button.active {{ background:#1769d2; color:white; border-color:#1769d2 }} input {{ flex:1; min-width:200px }}
.summary {{ color:#526278; font-size:.92rem }} .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr)); gap:1rem }}
.card {{ background:white; border:1px solid #dce3ed; border-radius:.8rem; padding:1.25rem; box-shadow:0 2px 9px #10233f09 }} .meta {{ display:flex; flex-wrap:wrap; align-items:center; gap:.45rem; color:#526278; font-size:.79rem }}
.tag {{ background:#e6efff; color:#174e9b; padding:.2rem .45rem; border-radius:.3rem; font-weight:700 }} h2 {{ font-size:1.1rem; line-height:1.4; margin:.9rem 0 .2rem }} a {{ color:#122d51; text-decoration:none }} a:hover {{ text-decoration:underline }}
.warning {{ padding:1rem; background:#fff3d5; border-radius:.5rem }} footer {{ margin-top:2rem; color:#526278; font-size:.85rem }}
</style></head><body><header><div>NEWS INTELLIGENCE</div><h1>Market Signal Monitor</h1><p>Recent market, business, political, and economic headlines from GDELT's news index and official feeds. Open each publisher's story for the full context.</p></header>
<main><div class="toolbar"><button type="button" class="active" data-filter="All">All</button>{buttons}<input id="search" type="search" placeholder="Search headlines or sources" aria-label="Search headlines or sources"></div>
<p class="summary"><span id="count">{len(items)}</span> stories in archive · Updated {e(updated)} UTC · Times shown in UTC</p>{warning}
<section class="grid" id="stories">{cards}</section><p id="empty" hidden>No matching stories.</p>
<footer>Headlines are links to external publishers. Coverage is incomplete and may contain duplicates or errors; verify important claims at the source. This is news discovery, not financial advice.</footer></main>
<script>const cards=[...document.querySelectorAll('.card')], buttons=[...document.querySelectorAll('[data-filter]')], search=document.querySelector('#search'); let category='All'; function filter() {{let n=0; for(const card of cards) {{const shown=(category==='All'||card.dataset.category===category)&&card.dataset.search.toLowerCase().includes(search.value.toLowerCase()); card.hidden=!shown; n+=shown;}} document.querySelector('#count').textContent=n;document.querySelector('#empty').hidden=n!==0;}} buttons.forEach(b=>b.addEventListener('click',()=>{{category=b.dataset.filter;buttons.forEach(x=>x.classList.toggle('active',x===b));filter();}}));search.addEventListener('input',filter);</script></body></html>'''


def run(config_path: Path, output: Path, archive: Path) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    categories = config["categories"]
    incoming, errors = [], []
    for category, query in categories.items():
        try:
            incoming.extend(parse_gdelt(fetch(gdelt_url(query, config["lookback"], config["max_records_per_category"])), category))
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{category}: {type(exc).__name__}")
    for feed in config.get("feeds", []):
        try:
            incoming.extend(parse_rss(fetch(feed["url"]), feed["name"], feed["category"]))
        except (urllib.error.URLError, TimeoutError, ValueError, ET.ParseError) as exc:
            errors.append(f"{feed['name']}: {type(exc).__name__}")
    if not incoming and not archive.exists():
        print("No stories available; " + "; ".join(errors), file=sys.stderr)
        return 1
    existing = json.loads(archive.read_text(encoding="utf-8")) if archive.exists() else []
    items = merge(existing, incoming, config["max_archive_items"])
    updated = datetime.now(timezone.utc).isoformat(timespec="minutes")
    output.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "index.html").write_text(render(items, updated, errors, list(categories)), encoding="utf-8")
    (output / "stories.json").write_text(json.dumps({"updated": updated, "errors": errors, "stories": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(items)} stories ({len(incoming)} fetched); {len(errors)} source errors")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("docs"))
    parser.add_argument("--archive", type=Path, default=Path(__file__).with_name("data") / "articles.json")
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.output, args.archive))

from __future__ import annotations

import email.utils
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html import unescape

from common import STATE_DIR, dump_json, ensure_dirs, load_config, now_cst

UA = "Mozilla/5.0 (compatible; feishu-bots-briefing/1.0; +https://github.com/)"


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_dt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone(timedelta(hours=8))).isoformat()
    except Exception:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone(timedelta(hours=8))).isoformat()
        except Exception:
            continue
    return None


def parse_relative_cn(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    now = now_cst()
    if text == "刚刚":
        return now.isoformat()
    patterns = [
        (r"(\d+)\s*分钟前", "minutes"),
        (r"(\d+)\s*小时前", "hours"),
        (r"(\d+)\s*天前", "days"),
    ]
    for pat, unit in patterns:
        match = re.search(pat, text)
        if not match:
            continue
        amount = int(match.group(1))
        if unit == "minutes":
            return (now - timedelta(minutes=amount)).isoformat()
        if unit == "hours":
            return (now - timedelta(hours=amount)).isoformat()
        if unit == "days":
            return (now - timedelta(days=amount)).isoformat()
    return None


def within_window(iso_dt: str | None, hours: int) -> bool:
    if not iso_dt:
        return True
    try:
        dt = datetime.fromisoformat(iso_dt)
        return dt >= now_cst() - timedelta(hours=hours)
    except Exception:
        return True


def sort_key(item: dict) -> tuple[float, str, str]:
    published = item.get("published_at")
    if published:
        try:
            dt = datetime.fromisoformat(published)
            return (dt.timestamp(), item.get("source_name") or "", item.get("title") or "")
        except Exception:
            pass
    return (0.0, item.get("source_name") or "", item.get("title") or "")


def normalize_title(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"^[^\w\u4e00-\u9fffA-Za-z]+", "", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_rss(source: dict, hours: int) -> list[dict]:
    xml = fetch_text(source["url"])
    root = ET.fromstring(xml)
    items: list[dict] = []
    for item in root.findall(".//item")[:12]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = parse_dt(item.findtext("pubDate"))
        desc = clean_text(item.findtext("description") or "")
        if not title or not link or not within_window(pub, hours):
            continue
        items.append(
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "category": source["category"],
                    "title": title,
                    "url": link,
                    "published_at": pub,
                    "summary": desc[:320],
            }
        )
    return items


def fetch_html_json(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    items: list[dict] = []
    if source["id"] == "the_neuron":
        pat = re.compile(r'<a[^>]+href="(/p/[^"]+)"[^>]*>.*?<time dateTime="([^"]+)">[^<]+</time>.*?<h2[^>]*>([^<]+)</h2>', re.S)
        seen: set[str] = set()
        for href, published, title in pat.findall(text):
            if href in seen:
                continue
            seen.add(href)
            url = f"https://www.theneurondaily.com{href}"
            pub = parse_dt(published)
            if not title or not within_window(pub, hours):
                continue
            try:
                article = fetch_text(url)
            except Exception:
                article = ""
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', article)
            items.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": normalize_title(title),
                    "url": url,
                    "published_at": pub,
                    "summary": clean_text(desc_match.group(1))[:320] if desc_match else "",
                }
            )
            if len(items) >= 6:
                break
        return items
    if source["id"] == "superhuman_ai":
        cards = re.findall(r'<a href="(/p/[^"]+)" class="relative z-10 embla__slide__number">', text)
        seen: set[str] = set()
        for href in cards:
            if href in seen:
                continue
            seen.add(href)
            url = f"https://www.superhuman.ai{href}"
            try:
                article = fetch_text(url)
            except Exception:
                continue
            title_match = re.search(r'<title>([^<]+)</title>', article)
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', article)
            published_match = re.search(r'"datePublished":"([^"]+)"', article)
            title = normalize_title(title_match.group(1).replace(" | Superhuman AI", "")) if title_match else ""
            pub = parse_dt(published_match.group(1)) if published_match else None
            if not title or not within_window(pub, hours):
                continue
            items.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": url,
                    "published_at": pub,
                    "summary": clean_text(desc_match.group(1))[:320] if desc_match else "",
                }
            )
            if len(items) >= 6:
                break
        return items
    if source["id"] == "toools_design":
        pat = re.compile(
            r'<a href="(/newsletter/issues/[^"]+)" class="card_global issue-highlight w-inline-block">.*?<div class="newsletter__section-label">([^<]+)</div>.*?<h3[^>]*>([^<]+)</h3>.*?<p[^>]*>([^<]+)</p>',
            re.S,
        )
        seen: set[str] = set()
        for href, published_text, title, summary in pat.findall(text):
            if href in seen:
                continue
            seen.add(href)
            url = f"https://www.toools.design{href}"
            pub = parse_dt(published_text.strip().replace(",", ""))
            if not title or not within_window(pub, hours * 3):
                continue
            items.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": normalize_title(title),
                    "url": url,
                    "published_at": pub,
                    "summary": clean_text(summary)[:320],
                }
            )
            if len(items) >= 4:
                break
        return items
    if source["id"] == "the_rundown_ai":
        cards = re.findall(r'<a href="(/p/[^"]+)" class="relative z-10 h-full embla__slide__number">', text)
        seen: set[str] = set()
        for href in cards:
            if href in seen:
                continue
            seen.add(href)
            url = f"https://www.therundown.ai{href}"
            try:
                article = fetch_text(url)
            except Exception:
                continue
            title_match = re.search(r'<title>([^<]+)</title>', article)
            published_match = re.search(r'"datePublished":"([^"]+)"', article)
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', article)
            title = normalize_title(title_match.group(1).replace(" | The Rundown AI", "")) if title_match else ""
            pub = parse_dt(published_match.group(1)) if published_match else None
            if not title or not within_window(pub, hours):
                continue
            items.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": url,
                    "published_at": pub,
                    "summary": clean_text(desc_match.group(1))[:320] if desc_match else "",
                }
            )
            if len(items) >= 6:
                break
        return items
    if source["id"] == "futurepedia_newsletter":
        pat = re.compile(
            r'<a href="(https://newsletter\.futurepedia\.io/p/[^"]+)".*?<time dateTime="([^"]+)">[^<]+</time>.*?<h3[^>]*><span class="absolute inset-0"></span>([^<]+)</h3>',
            re.S,
        )
        for url, published, title in pat.findall(text):
            pub = parse_dt(published)
            if not title or not url or not within_window(pub, hours):
                continue
            items.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": normalize_title(title),
                    "url": url,
                    "published_at": pub,
                    "summary": "",
                }
            )
            if len(items) >= 10:
                break
        return items

    pat = re.compile(source["item_pattern"], re.S)
    for match in pat.finditer(text):
        groups = match.groups()
        if len(groups) < 3:
            continue
        a, b, c = groups[:3]
        # normalize field order per source
        if source["id"] == "the_batch":
            title, slug, published = a, b, c
            url = f"https://www.deeplearning.ai/the-batch/{slug}/"
        else:
            url, title, published = a, b, c
        pub = parse_dt(published)
        if not title or not url or not within_window(pub, hours):
            continue
        items.append(
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "category": source["category"],
                "title": normalize_title(title),
                "url": url,
                "published_at": pub,
                "summary": "",
            }
        )
        if len(items) >= 10:
            break
    return items


def fetch_html_list(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    items: list[dict] = []
    pat = source.get("title_pattern")
    if pat:
        for match in re.finditer(pat, text, re.S):
            g1, g2 = match.groups()[:2]
            if source["id"] == "cursor_blog":
                title, href = g1, g2
            else:
                href, title = g1, g2
            url = href if href.startswith("http") else f"https://cursor.com{href}" if source["id"] == "cursor_blog" else f"https://tldr.tech{href}"
            published_at = None
            if source["id"] == "tldr_ai":
                match_date = re.search(r"/ai/(\d{4}-\d{2}-\d{2})", url)
                if match_date:
                    published_at = parse_dt(match_date.group(1))
                    if not within_window(published_at, hours):
                        continue
            items.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": normalize_title(title),
                    "url": url,
                    "published_at": published_at,
                    "summary": "",
                }
            )
            if len(items) >= 10:
                break
    return items


def fetch_html_card(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    pat = re.compile(
        r'<h2 class="item-title"><a title="([^"]+)" href="([^"]+)"[^>]*>([^<]+)</a></h2>.*?<span>([^<]{10,220})</span>.*?<span class="meta-time">([^<]+)</span>',
        re.S,
    )
    items: list[dict] = []
    for title_attr, href, title_text, summary, rel_time in pat.findall(text):
        title = normalize_title(title_text or title_attr)
        if not title:
            continue
        rel_time_clean = rel_time.strip()
        published_at = parse_relative_cn(rel_time_clean) or parse_dt(rel_time_clean)
        if not within_window(published_at, hours):
            continue
        items.append(
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "category": source["category"],
                "title": title,
                "url": href,
                "published_at": published_at or rel_time,
                "summary": clean_text(summary)[:320],
            }
        )
        if len(items) >= 8:
            break
    return items


def fetch_html_feed(source: dict, hours: int) -> list[dict]:
    # Some "feed" pages are actually HTML archives. Extract current day cards.
    text = fetch_text(source["url"])
    target_day = now_cst().strftime("%A, %B ").replace(" 0", " ") + str(now_cst().day)
    if target_day in text:
        section_start = text.find(target_day)
        next_section = text.find('class="pt-16 md:pt-24 pb-8"', section_start + 1)
        text = text[section_start: next_section if next_section != -1 else len(text)]
    pat = re.compile(
        r'<a href="([^"]+)"[^>]*class="group block rise[^"]*".*?<h3[^>]*><span class="signal-underline">([^<]+)</span></h3>.*?<p[^>]*>([^<]+)</p>.*?<div class="col-span-12 md:col-span-3 label text-muted pt-2 md:text-right">([^<]*)</div>',
        re.S,
    )
    items: list[dict] = []
    for href, title, summary, source_site in pat.findall(text):
        items.append(
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "category": source["category"],
                "title": normalize_title(title),
                "url": href,
                "published_at": None,
                "summary": clean_text(summary)[:320],
                "origin_site": clean_text(source_site),
            }
        )
        if len(items) >= 10:
            break
    return items


def fetch_source(source: dict, hours: int) -> dict:
    try:
        kind = source["type"]
        if kind == "rss":
            items = fetch_rss(source, hours)
        elif kind == "html_json":
            items = fetch_html_json(source, hours)
        elif kind == "html_list":
            items = fetch_html_list(source, hours)
        elif kind == "html_card":
            items = fetch_html_card(source, hours)
        elif kind == "html_feed":
            items = fetch_html_feed(source, hours)
        else:
            raise ValueError(f"unsupported source type: {kind}")
        return {"source": source["name"], "ok": True, "count": len(items), "items": items}
    except Exception as exc:
        return {"source": source["name"], "ok": False, "error": str(exc), "items": []}


def main() -> int:
    ensure_dirs()
    cfg = load_config()
    hours = int(cfg.get("time_window_hours", 72))
    results = [fetch_source(src, hours) for src in cfg["sources"] if src.get("enabled", True)]
    out = {
        "generated_at": now_cst().isoformat(),
        "results": results,
        "items": [item for result in results for item in result["items"]],
    }
    out["items"].sort(key=sort_key, reverse=True)
    dump_json(STATE_DIR / "fetched.json", out)
    print(json.dumps({"sources": len(results), "items": len(out["items"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

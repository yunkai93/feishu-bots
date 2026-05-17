from __future__ import annotations

import email.utils
import json
import re
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


def clean_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"^[^\w\u4e00-\u9fffA-Za-z]+", "", text)
    return text.strip()


def normalize_url(url: str) -> str:
    url = url.strip()
    if "?" in url:
        url = url.split("?", 1)[0]
    return url.rstrip("/")


def item_keywords(item: dict) -> str:
    parts = [
        item.get("title", ""),
        item.get("summary", ""),
        item.get("source_name", ""),
        item.get("origin_site", ""),
    ]
    return " ".join(parts).lower()


def quality_score(item: dict, preferred_entities: list[str]) -> float:
    source_priority = float(item.get("source_priority", 0))
    recency_bonus = 0.0
    published = item.get("published_at")
    if published:
        try:
            dt = datetime.fromisoformat(published)
            age_hours = max((now_cst() - dt).total_seconds() / 3600, 0)
            recency_bonus = max(0.0, 48.0 - min(age_hours, 48.0))
        except Exception:
            recency_bonus = 0.0
    text = item_keywords(item)
    entity_hits = sum(1 for name in preferred_entities if name.lower() in text)
    design_bonus = 0.0
    if item.get("category") == "design":
        if any(key in text for key in ["figma", "canva", "design", "workflow", "interface", "brand", "ui", "ux"]):
            design_bonus = 12.0
        if any(key in text for key in ["best ai art generators", "signed away all of our ideas", "designers have"]):
            design_bonus -= 18.0
    agent_bonus = 0.0
    if item.get("category") == "agent":
        if any(key in text for key in ["agent", "codex", "claude code", "cursor", "mcp", "notion", "browser", "computer use"]):
            agent_bonus = 12.0
    summary_bonus = min(len(item.get("summary", "")) / 40.0, 8.0)
    tier_bonus = {
        "daily_brief": 12.0,
        "builder_brief": 9.0,
        "design_brief": 8.0,
        "deep_dive": 4.0,
    }.get(item.get("source_tier", ""), 0.0)
    return source_priority + recency_bonus + entity_hits * 10.0 + design_bonus + agent_bonus + summary_bonus + tier_bonus


def sort_key(item: dict) -> tuple[float, float, str]:
    published_ts = 0.0
    published = item.get("published_at")
    if published:
        try:
            published_ts = datetime.fromisoformat(published).timestamp()
        except Exception:
            published_ts = 0.0
    return (float(item.get("quality_score", 0.0)), published_ts, item.get("title") or "")


def enrich_item(source: dict, item: dict) -> dict:
    enriched = dict(item)
    enriched["title"] = normalize_title(enriched.get("title", ""))
    enriched["url"] = normalize_url(enriched.get("url", ""))
    enriched["source_priority"] = source.get("priority", 0)
    enriched["source_tier"] = source.get("tier", "")
    enriched["source_max_items"] = source.get("max_items", 0)
    enriched["freshness_hours"] = source.get("freshness_hours", 72)
    return enriched


def dedupe_items(items: list[dict], preferred_entities: list[str]) -> list[dict]:
    best_by_url: dict[str, dict] = {}
    best_by_title: dict[str, dict] = {}
    for item in items:
        item["quality_score"] = quality_score(item, preferred_entities)
        url_key = item.get("url", "")
        title_key = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", item.get("title", "").lower())
        existing = best_by_url.get(url_key) if url_key else None
        if existing is None or item["quality_score"] > existing["quality_score"]:
            if url_key:
                best_by_url[url_key] = item
        existing = best_by_title.get(title_key) if title_key else None
        if existing is None or item["quality_score"] > existing["quality_score"]:
            if title_key:
                best_by_title[title_key] = item

    chosen: dict[int, dict] = {}
    for item in best_by_url.values():
        chosen[id(item)] = item
    for item in best_by_title.values():
        chosen[id(item)] = item

    result = list(chosen.values())
    result = [item for item in result if item.get("quality_score", 0) >= 70]
    result.sort(key=sort_key, reverse=True)
    return result


def limit_per_source(items: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    result: list[dict] = []
    for item in items:
        source_id = item.get("source_id", "")
        max_items = int(item.get("source_max_items", 99) or 99)
        counts[source_id] = counts.get(source_id, 0)
        if counts[source_id] >= max_items:
            continue
        counts[source_id] += 1
        result.append(item)
    return result


def fetch_rss(source: dict, hours: int) -> list[dict]:
    xml = fetch_text(source["url"])
    root = ET.fromstring(xml)
    items: list[dict] = []
    max_scan = max(int(source.get("max_items", 8)) * 3, 12)
    for item in root.findall(".//item")[:max_scan]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = parse_dt(item.findtext("pubDate"))
        desc = clean_text(item.findtext("description") or "")
        if not title or not link or not within_window(pub, int(source.get("freshness_hours", hours))):
            continue
        items.append(
            enrich_item(
                source,
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": link,
                    "published_at": pub,
                    "summary": desc[:320],
                },
            )
        )
    return items


def fetch_html_json(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    items: list[dict] = []
    freshness_hours = int(source.get("freshness_hours", hours))
    max_items = int(source.get("max_items", 6))

    if source["id"] == "the_neuron":
        pat = re.compile(r'<a[^>]+href="(/p/[^"]+)"[^>]*>.*?<time dateTime="([^"]+)">[^<]+</time>.*?<h2[^>]*>([^<]+)</h2>', re.S)
        seen: set[str] = set()
        for href, published, title in pat.findall(text):
            if href in seen:
                continue
            seen.add(href)
            url = f"https://www.theneurondaily.com{href}"
            pub = parse_dt(published)
            if not title or not within_window(pub, freshness_hours):
                continue
            try:
                article = fetch_text(url)
            except Exception:
                article = ""
            desc_match = re.search(r'<meta name="description" content="([^"]+)"', article)
            items.append(
                enrich_item(
                    source,
                    {
                        "source_id": source["id"],
                        "source_name": source["name"],
                        "category": source["category"],
                        "title": title,
                        "url": url,
                        "published_at": pub,
                        "summary": clean_text(desc_match.group(1))[:320] if desc_match else "",
                    },
                )
            )
            if len(items) >= max_items:
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
            if not title or not within_window(pub, freshness_hours):
                continue
            items.append(
                enrich_item(
                    source,
                    {
                        "source_id": source["id"],
                        "source_name": source["name"],
                        "category": source["category"],
                        "title": title,
                        "url": url,
                        "published_at": pub,
                        "summary": clean_text(desc_match.group(1))[:320] if desc_match else "",
                    },
                )
            )
            if len(items) >= max_items:
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
            if not title or not within_window(pub, freshness_hours):
                continue
            items.append(
                enrich_item(
                    source,
                    {
                        "source_id": source["id"],
                        "source_name": source["name"],
                        "category": source["category"],
                        "title": title,
                        "url": url,
                        "published_at": pub,
                        "summary": clean_text(summary)[:320],
                    },
                )
            )
            if len(items) >= max_items:
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
            if not title or not within_window(pub, freshness_hours):
                continue
            items.append(
                enrich_item(
                    source,
                    {
                        "source_id": source["id"],
                        "source_name": source["name"],
                        "category": source["category"],
                        "title": title,
                        "url": url,
                        "published_at": pub,
                        "summary": clean_text(desc_match.group(1))[:320] if desc_match else "",
                    },
                )
            )
            if len(items) >= max_items:
                break
        return items

    if source["id"] == "futurepedia_newsletter":
        pat = re.compile(
            r'<a href="(https://newsletter\.futurepedia\.io/p/[^"]+)".*?<time dateTime="([^"]+)">[^<]+</time>.*?<h3[^>]*><span class="absolute inset-0"></span>([^<]+)</h3>',
            re.S,
        )
        for url, published, title in pat.findall(text):
            pub = parse_dt(published)
            if not title or not url or not within_window(pub, freshness_hours):
                continue
            items.append(
                enrich_item(
                    source,
                    {
                        "source_id": source["id"],
                        "source_name": source["name"],
                        "category": source["category"],
                        "title": title,
                        "url": url,
                        "published_at": pub,
                        "summary": "",
                    },
                )
            )
            if len(items) >= max_items:
                break
        return items

    pat = re.compile(source["item_pattern"], re.S)
    for match in pat.finditer(text):
        groups = match.groups()
        if len(groups) < 3:
            continue
        a, b, c = groups[:3]
        if source["id"] == "the_batch":
            title, slug, published = a, b, c
            url = f"https://www.deeplearning.ai/the-batch/{slug}/"
        else:
            url, title, published = a, b, c
        pub = parse_dt(published)
        if not title or not url or not within_window(pub, freshness_hours):
            continue
        items.append(
            enrich_item(
                source,
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": url,
                    "published_at": pub,
                    "summary": "",
                },
            )
        )
        if len(items) >= max_items:
            break
    return items


def fetch_html_card(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    pat = re.compile(
        r'<h2 class="item-title"><a title="([^"]+)" href="([^"]+)"[^>]*>([^<]+)</a></h2>.*?<span>([^<]{10,220})</span>.*?<span class="meta-time">([^<]+)</span>',
        re.S,
    )
    items: list[dict] = []
    freshness_hours = int(source.get("freshness_hours", hours))
    max_items = int(source.get("max_items", 6))
    for title_attr, href, title_text, summary, rel_time in pat.findall(text):
        title = normalize_title(title_text or title_attr)
        if not title:
            continue
        rel_time_clean = rel_time.strip()
        published_at = parse_relative_cn(rel_time_clean) or parse_dt(rel_time_clean)
        if not within_window(published_at, freshness_hours):
            continue
        items.append(
            enrich_item(
                source,
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": href,
                    "published_at": published_at or rel_time,
                    "summary": clean_text(summary)[:320],
                },
            )
        )
        if len(items) >= max_items:
            break
    return items


def fetch_html_feed(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    pat = re.compile(
        r'<a href="([^"]+)"[^>]*class="group block rise[^"]*".*?<h3[^>]*><span class="signal-underline">([^<]+)</span></h3>.*?<p[^>]*>([^<]+)</p>.*?<div class="col-span-12 md:col-span-3 label text-muted pt-2 md:text-right">([^<]*)</div>',
        re.S,
    )
    items: list[dict] = []
    max_items = int(source.get("max_items", 8))
    for href, title, summary, source_site in pat.findall(text):
        items.append(
            enrich_item(
                source,
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": href,
                    "published_at": None,
                    "summary": clean_text(summary)[:320],
                    "origin_site": clean_text(source_site),
                },
            )
        )
        if len(items) >= max_items:
            break
    return items


def fetch_source(source: dict, hours: int) -> dict:
    try:
        kind = source["type"]
        if kind == "rss":
            items = fetch_rss(source, hours)
        elif kind == "html_json":
            items = fetch_html_json(source, hours)
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
    preferred_entities = list(cfg.get("preferred_entities", []))
    results = [fetch_source(src, hours) for src in cfg["sources"] if src.get("enabled", True)]
    raw_items = [item for result in results for item in result["items"]]
    deduped = dedupe_items(raw_items, preferred_entities)
    final_items = limit_per_source(deduped)
    out = {
        "generated_at": now_cst().isoformat(),
        "results": results,
        "items": final_items,
    }
    dump_json(STATE_DIR / "fetched.json", out)
    print(json.dumps({"sources": len(results), "items": len(final_items)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

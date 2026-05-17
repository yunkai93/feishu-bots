from __future__ import annotations

import email.utils
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone(timedelta(hours=8))).isoformat()
    except Exception:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
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
    raw = url.strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower()
        not in {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "ref",
            "ref_src",
            "fbclid",
            "gclid",
            "mc_cid",
            "mc_eid",
        }
    ]
    path = parts.path.rstrip("/") or parts.path
    query = urlencode(filtered_query, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def filter_text(item: dict) -> str:
    parts = [
        item.get("title", ""),
        item.get("summary", ""),
        item.get("source_name", ""),
        item.get("origin_site", ""),
        item.get("url", ""),
        " ".join(item.get("tags", [])),
    ]
    return clean_text(" ".join(parts)).lower()


def matches_patterns(patterns: list[str], title: str, text: str) -> bool:
    return any(re.search(pattern, title, re.I) or re.search(pattern, text, re.I) for pattern in patterns)


def passes_source_filters(source: dict, item: dict) -> bool:
    title = item.get("title", "")
    text = filter_text(item)
    include_keywords = [str(value).lower() for value in source.get("include_keywords", [])]
    exclude_keywords = [str(value).lower() for value in source.get("exclude_keywords", [])]
    include_patterns = [str(value) for value in source.get("include_patterns", [])]
    exclude_patterns = [str(value) for value in source.get("exclude_patterns", [])]

    if include_keywords and not any(keyword in text for keyword in include_keywords):
        return False
    if include_patterns and not matches_patterns(include_patterns, title, text):
        return False
    if exclude_keywords and any(keyword in text for keyword in exclude_keywords):
        return False
    if exclude_patterns and matches_patterns(exclude_patterns, title, text):
        return False
    return True


def item_keywords(item: dict) -> str:
    parts = [
        item.get("title", ""),
        item.get("summary", ""),
        item.get("source_name", ""),
        item.get("origin_site", ""),
        " ".join(item.get("tags", [])),
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
        if any(
            key in text
            for key in [
                "figma",
                "canva",
                "claude design",
                "gpt image 2",
                "photoshop",
                "firefly",
                "midjourney",
                "runway",
                "lovart",
                "即梦",
                "可灵",
                "seedance",
                "设计",
                "工作流",
                "原型",
                "修图",
                "生图",
                "海报",
                "logo",
                "banner",
                "ppt",
                "界面",
                "ui",
                "ux",
            ]
        ):
            design_bonus += 12.0
        if any(
            key in text
            for key in [
                "中文",
                "优设",
                "uisdc",
                "教程",
                "案例",
                "实操",
                "拆解",
                "技巧",
                "提示词",
                "交付",
                "工作流",
            ]
        ):
            design_bonus += 18.0
        if item.get("source_name") in {"UISDC AIGC", "UISDC AI头条", "UISDC 首页精选"}:
            design_bonus += 14.0
        if item.get("source_name") in {"AI in Design", "TOOOLS"}:
            design_bonus -= 6.0
        if any(key in text for key in ["best ai art generators", "signed away all of our ideas", "designers have"]):
            design_bonus -= 18.0
        if any(
            key in text
            for key in [
                "课程",
                "训练营",
                "财报",
                "融资",
                "招聘",
                "conference",
                "podcast",
                "伦理",
                "copyright settlement",
            ]
        ):
            design_bonus -= 14.0
    agent_bonus = 0.0
    if item.get("category") == "agent":
        if any(key in text for key in ["agent", "codex", "claude code", "cursor", "mcp", "notion", "browser", "computer use"]):
            agent_bonus = 12.0
    platform_bonus = 0.0
    if any(
        key in text
        for key in [
            "release",
            "release notes",
            "available",
            "launch",
            "rollout",
            "mobile",
            "app",
            "proxy",
            "api",
            "integration",
            "mcp",
            "workflow",
            "whiteboard",
            "figjam",
            "make",
        ]
    ):
        platform_bonus += 6.0
    noise_penalty = 0.0
    if any(
        key in text
        for key in [
            "podcast",
            "course",
            "competition",
            "forum",
            "careers",
            "hiring",
            "job",
            "jobs",
            "salary",
            "livestream",
            "paper roundup",
        ]
    ):
        noise_penalty -= 12.0
    if item.get("category") == "design" and item.get("source_name") in {"UISDC AIGC", "UISDC AI头条"}:
        noise_penalty += 6.0
    summary_bonus = min(len(item.get("summary", "")) / 40.0, 8.0)
    tier_bonus = {
        "daily_brief": 12.0,
        "builder_brief": 9.0,
        "design_brief": 8.0,
        "deep_dive": 4.0,
        "official_feed": 11.0,
        "project_watch": 15.0,
    }.get(item.get("source_tier", ""), 0.0)
    return (
        source_priority
        + recency_bonus
        + entity_hits * 10.0
        + design_bonus
        + agent_bonus
        + platform_bonus
        + summary_bonus
        + tier_bonus
        + noise_penalty
    )


def sort_key(item: dict) -> tuple[float, float, str]:
    published_ts = 0.0
    published = item.get("published_at")
    if published:
        try:
            published_ts = datetime.fromisoformat(published).timestamp()
        except Exception:
            published_ts = 0.0
    return (float(item.get("quality_score", 0.0)), published_ts, item.get("title") or "")


def enrich_item(source: dict, item: dict) -> dict | None:
    enriched = dict(item)
    enriched["title"] = normalize_title(enriched.get("title", ""))
    enriched["url"] = normalize_url(enriched.get("url", ""))
    enriched["source_priority"] = source.get("priority", 0)
    enriched["source_tier"] = source.get("tier", "")
    enriched["source_max_items"] = source.get("max_items", 0)
    enriched["freshness_hours"] = source.get("freshness_hours", 72)
    if not enriched["title"] or not enriched["url"]:
        return None
    if not passes_source_filters(source, enriched):
        return None
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
        tags = [clean_text(node.text or "") for node in item.findall("category") if clean_text(node.text or "")]
        if not title or not link or not within_window(pub, int(source.get("freshness_hours", hours))):
            continue
        enriched = enrich_item(
            source,
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "category": source["category"],
                "title": title,
                "url": link,
                "published_at": pub,
                "summary": desc[:320],
                "tags": tags,
            },
        )
        if enriched:
            items.append(enriched)
    return items


def fetch_atom(source: dict, hours: int) -> list[dict]:
    xml = fetch_text(source["url"])
    root = ET.fromstring(xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict] = []
    freshness_hours = int(source.get("freshness_hours", hours))
    max_scan = max(int(source.get("max_items", 8)) * 3, 12)

    for entry in root.findall("atom:entry", ns)[:max_scan]:
        title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))
        link = ""
        for node in entry.findall("atom:link", ns):
            href = (node.attrib.get("href") or "").strip()
            rel = (node.attrib.get("rel") or "alternate").strip()
            if href and rel == "alternate":
                link = href
                break
            if href and not link:
                link = href
        published = (
            parse_dt(entry.findtext("atom:published", default=None, namespaces=ns))
            or parse_dt(entry.findtext("atom:updated", default=None, namespaces=ns))
        )
        summary = clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
        if not summary:
            summary = clean_text(entry.findtext("atom:content", default="", namespaces=ns))
        tags = [
            clean_text((node.attrib.get("term") or node.text or ""))
            for node in entry.findall("atom:category", ns)
            if clean_text((node.attrib.get("term") or node.text or ""))
        ]
        if not title or not link or not within_window(published, freshness_hours):
            continue
        enriched = enrich_item(
            source,
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "category": source["category"],
                "title": title,
                "url": link,
                "published_at": published,
                "summary": summary[:900],
                "tags": tags,
            },
        )
        if enriched:
            items.append(enriched)
        if len(items) >= int(source.get("max_items", 8)):
            break
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
            enriched = enrich_item(
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
            if enriched:
                items.append(enriched)
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
            enriched = enrich_item(
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
            if enriched:
                items.append(enriched)
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
            enriched = enrich_item(
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
            if enriched:
                items.append(enriched)
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
            enriched = enrich_item(
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
            if enriched:
                items.append(enriched)
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
            enriched = enrich_item(
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
            if enriched:
                items.append(enriched)
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
        enriched = enrich_item(
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
        if enriched:
            items.append(enriched)
        if len(items) >= max_items:
            break
    return items


def fetch_html_card(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    if source["id"] == "uisdc_aigc_tag":
        card_pat = re.compile(
            r'<div class="category-list-item[^"]*?item-wrap">.*?<h2 class="item-title">\s*<a title="([^"]+)" href="([^"]+)"[^>]*>.*?</a>.*?<i class="meta-time">\s*([^<]+)\s*</i>.*?<a class="tag[^"]*" title="([^"]+)"',
            re.S,
        )
        items: list[dict] = []
        freshness_hours = int(source.get("freshness_hours", hours))
        max_items = int(source.get("max_items", 6))
        for title, href, rel_time, tag in card_pat.findall(text):
            published_at = parse_relative_cn(rel_time.strip()) or parse_dt(rel_time.strip())
            if not within_window(published_at, freshness_hours):
                continue
            enriched = enrich_item(
                source,
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": href,
                    "published_at": published_at or rel_time.strip(),
                    "summary": clean_text(tag)[:120],
                    "tags": [clean_text(tag)],
                },
            )
            if enriched:
                items.append(enriched)
            if len(items) >= max_items:
                break
        return items

    if source["id"] == "uisdc_aigc365":
        day_pat = re.compile(
            r'<h5 class="i-date">([^<]+)</h5><div class="i-items">(.*?)</div></div></div>',
            re.S,
        )
        item_pat = re.compile(
            r'<a class="i-item" href="([^"]+)"[^>]*>.*?<h2 class="i-title">([^<]+)</h2>.*?<div class="i-tag[^"]*">([^<]+)</div>',
            re.S,
        )
        items: list[dict] = []
        freshness_hours = int(source.get("freshness_hours", hours))
        max_items = int(source.get("max_items", 6))
        for date_text, block in day_pat.findall(text):
            published_at = parse_dt(date_text.strip())
            if not within_window(published_at, freshness_hours):
                continue
            for href, title, tag in item_pat.findall(block):
                enriched = enrich_item(
                    source,
                    {
                        "source_id": source["id"],
                        "source_name": source["name"],
                        "category": source["category"],
                        "title": clean_text(title),
                        "url": href,
                        "published_at": published_at or date_text.strip(),
                        "summary": clean_text(tag)[:120],
                        "tags": [clean_text(tag)],
                    },
                )
                if enriched:
                    items.append(enriched)
                if len(items) >= max_items:
                    return items
        return items

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
        enriched = enrich_item(
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
        if enriched:
            items.append(enriched)
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
        enriched = enrich_item(
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
        if enriched:
            items.append(enriched)
        if len(items) >= max_items:
            break
    return items


def fetch_uisdc_news(source: dict, hours: int) -> list[dict]:
    text = fetch_text(source["url"])
    match = re.search(r'var\s+uisdc_news\s*=\s*"((?:\\.|[^"])*)";', text, re.S)
    if not match:
        return []
    try:
        payload = json.loads(f'"{match.group(1)}"')
        blocks = json.loads(payload)
    except Exception:
        return []
    dump_json(
        STATE_DIR / "uisdc_news_raw.json",
        {
            "fetched_at": now_cst().isoformat(),
            "source": source["url"],
            "blocks": blocks,
        },
    )

    items: list[dict] = []
    freshness_hours = int(source.get("freshness_hours", hours))
    max_items = int(source.get("max_items", 4))
    for block in blocks:
        published_at = None
        try:
            published_at = datetime.fromtimestamp(int(block.get("time", 0)), tz=timezone(timedelta(hours=8))).isoformat()
        except Exception:
            published_at = None
        if not within_window(published_at, freshness_hours):
            continue
        for item in block.get("dubao", []):
            title = clean_text(item.get("title", ""))
            summary = clean_text(item.get("content", ""))
            image = clean_text((item.get("images") or "").split("|")[0])
            if not title:
                continue
            enriched = enrich_item(
                source,
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": item.get("url") or source["url"],
                    "published_at": published_at,
                    "summary": summary[:320],
                    "tags": [clean_text(item.get("title", ""))],
                    "origin_site": "优设读报",
                    "image": image,
                },
            )
            if enriched:
                items.append(enriched)
            if len(items) >= max_items:
                return items
    return items


def fetch_source(source: dict, hours: int) -> dict:
    try:
        kind = source["type"]
        if kind == "rss":
            items = fetch_rss(source, hours)
        elif kind == "atom":
            items = fetch_atom(source, hours)
        elif kind == "html_json":
            items = fetch_html_json(source, hours)
        elif kind == "html_card":
            items = fetch_html_card(source, hours)
        elif kind == "html_feed":
            items = fetch_html_feed(source, hours)
        elif kind == "uisdc_news":
            items = fetch_uisdc_news(source, hours)
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

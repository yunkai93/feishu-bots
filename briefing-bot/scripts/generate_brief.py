from __future__ import annotations

import json
import re
import subprocess

from common import PRODUCT_ROOT, PROMPT_FILE, SCHEMA_FILE, STATE_DIR, dump_json, ensure_dirs, load_json, now_cst


SOURCE_NORMALIZATION = {
    "Business Insider": "AI in Design",
    "Digital Trends": "AI in Design",
    "247WallSt": "AI in Design",
}

SECTION_TARGETS = {
    "agent_watch": {"category": "agent", "min": 4, "max": 6},
    "model_watch": {"category": "model", "min": 3, "max": 5},
    "design_ai": {"category": "design", "min": 4, "max": 6},
    "quick_radar": {"category": "ai", "min": 3, "max": 5},
}


def item_rank(item: dict) -> tuple[float, float, str]:
    score = float(item.get("quality_score", 0.0))
    published = item.get("published_at") or ""
    return (score, 0.0, published)


def normalize_brief_sources(brief: dict) -> dict:
    for section in ("agent_watch", "model_watch", "design_ai", "quick_radar"):
        for entry in brief.get(section, []):
            source = entry.get("source", "")
            if source in SOURCE_NORMALIZATION:
                entry["source"] = SOURCE_NORMALIZATION[source]
    brief["sources_used"] = [
        SOURCE_NORMALIZATION.get(source, source)
        for source in brief.get("sources_used", [])
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for source in brief["sources_used"]:
        if source in seen:
            continue
        seen.add(source)
        deduped.append(source)
    brief["sources_used"] = deduped
    return brief


def concise_title(item: dict) -> str:
    title = (item.get("title") or "").strip()
    title = title.replace("！", "，")
    title = title.replace("!", ",")
    title = title.replace("：", "，")
    parts = [part.strip(" ，,") for part in re.split(r"[!！:：]", title) if part.strip(" ，,")]
    return parts[0] if parts else title


def concise_summary(item: dict) -> str:
    summary = (item.get("summary") or "").strip()
    if not summary:
        return "这条值得继续跟进其对产品能力和工作流的实际影响。"
    parts = re.split(r"[。！？!?]", summary)
    first = next((part.strip() for part in parts if part.strip()), "")
    if not first:
        return summary[:70].strip()
    return first + "。"


def existing_titles(brief: dict) -> set[str]:
    used: set[str] = set()
    for section in SECTION_TARGETS:
        for entry in brief.get(section, []):
            title = (entry.get("title") or "").strip()
            if title:
                used.add(title)
    return used


def section_titles(brief: dict, section: str) -> set[str]:
    return {(entry.get("title") or "").strip() for entry in brief.get(section, []) if (entry.get("title") or "").strip()}


def candidate_entry(item: dict) -> dict:
    return {
        "title": concise_title(item),
        "summary": concise_summary(item),
        "source": item.get("source_name", ""),
        "url": item.get("url", ""),
    }


def expand_brief(brief: dict, items: list[dict]) -> dict:
    used_titles = existing_titles(brief)
    for section, rule in SECTION_TARGETS.items():
        current = list(brief.get(section, []))
        current_titles = section_titles(brief, section)
        need = max(rule["min"] - len(current), 0)
        if need <= 0:
            continue
        for item in items:
            if item.get("category") != rule["category"]:
                continue
            entry = candidate_entry(item)
            title = entry["title"]
            if not title or title in used_titles or title in current_titles:
                continue
            current.append(entry)
            current_titles.add(title)
            used_titles.add(title)
            if len(current) >= rule["min"]:
                break
        brief[section] = current[: rule["max"]]

    sources = list(brief.get("sources_used", []))
    seen = set(sources)
    for section in SECTION_TARGETS:
        for entry in brief.get(section, []):
            source = entry.get("source", "")
            if source and source not in seen:
                seen.add(source)
                sources.append(source)
    brief["sources_used"] = sources
    return brief


def build_payload(items: list[dict]) -> str:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    trimmed: list[dict] = []
    items = sorted(items, key=item_rank, reverse=True)
    category_limits = {"agent": 8, "model": 6, "design": 8, "ai": 8}
    used = {key: 0 for key in category_limits}
    tier_limits = {
        "project_watch": 5,
        "official_feed": 6,
        "daily_brief": 12,
        "builder_brief": 6,
        "design_brief": 8,
        "deep_dive": 5,
    }
    tier_used = {key: 0 for key in tier_limits}
    for item in items:
        cat = item.get("category", "ai")
        limit = category_limits.get(cat, 5)
        if used.get(cat, 0) >= limit:
            continue
        tier = item.get("source_tier", "")
        if tier in tier_limits and tier_used.get(tier, 0) >= tier_limits[tier]:
            continue
        trimmed.append(item)
        used[cat] = used.get(cat, 0) + 1
        if tier:
            tier_used[tier] = tier_used.get(tier, 0) + 1
        if len(trimmed) >= 28:
            break
    data = {
        "run_date": now_cst().strftime("%Y-%m-%d"),
        "items": trimmed,
    }
    return f"{prompt}\n\n输入数据：\n{json.dumps(data, ensure_ascii=False, indent=2)}\n"


def main() -> int:
    ensure_dirs()
    run_now = now_cst()
    fetched = load_json(STATE_DIR / "fetched.json", {"items": []})
    items = fetched.get("items", [])
    if not items:
        brief = {
            "date": run_now.strftime("%Y-%m-%d"),
            "updated_at": run_now.strftime("%Y-%m-%d %H:%M"),
            "today_take": "今天没有抓到足够的可用资讯，建议稍后重跑。",
            "agent_watch": [],
            "model_watch": [],
            "design_ai": [],
            "quick_radar": [],
            "follow_up": ["检查抓取源是否可访问，再次重跑。"],
            "sources_used": []
        }
        dump_json(STATE_DIR / "brief.json", brief)
        return 0

    payload = build_payload(items)
    result_path = STATE_DIR / "brief_raw.txt"
    cmd = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--ephemeral",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(PRODUCT_ROOT),
        "--output-schema",
        str(SCHEMA_FILE),
        "-o",
        str(result_path),
        "-"
    ]
    proc = subprocess.run(cmd, input=payload, text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout or "codex exec failed")

    raw = result_path.read_text(encoding="utf-8").strip()
    try:
        brief = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON from codex: {exc}\n{raw[:1000]}")

    brief = normalize_brief_sources(brief)
    brief = expand_brief(brief, items)
    brief = normalize_brief_sources(brief)
    brief["date"] = run_now.strftime("%Y-%m-%d")
    brief["updated_at"] = run_now.strftime("%Y-%m-%d %H:%M")
    dump_json(STATE_DIR / "brief.json", brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

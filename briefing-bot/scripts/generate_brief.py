from __future__ import annotations

import json
import subprocess

from common import PRODUCT_ROOT, PROMPT_FILE, SCHEMA_FILE, STATE_DIR, dump_json, ensure_dirs, load_json, now_cst


SOURCE_NORMALIZATION = {
    "Business Insider": "AI in Design",
    "Digital Trends": "AI in Design",
    "247WallSt": "AI in Design",
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


def build_payload(items: list[dict]) -> str:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    trimmed: list[dict] = []
    items = sorted(items, key=item_rank, reverse=True)
    category_limits = {"agent": 5, "model": 4, "design": 6, "ai": 6}
    used = {key: 0 for key in category_limits}
    tier_limits = {
        "daily_brief": 10,
        "builder_brief": 4,
        "design_brief": 6,
        "deep_dive": 4,
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
        if len(trimmed) >= 20:
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
    brief["date"] = run_now.strftime("%Y-%m-%d")
    brief["updated_at"] = run_now.strftime("%Y-%m-%d %H:%M")
    dump_json(STATE_DIR / "brief.json", brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

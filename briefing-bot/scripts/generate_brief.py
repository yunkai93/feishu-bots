from __future__ import annotations

import json
import subprocess

from common import PRODUCT_ROOT, PROMPT_FILE, SCHEMA_FILE, STATE_DIR, dump_json, ensure_dirs, load_json, now_cst


def build_payload(items: list[dict]) -> str:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    trimmed: list[dict] = []
    category_limits = {"agent": 6, "model": 6, "design": 8, "ai": 8}
    used = {key: 0 for key in category_limits}
    for item in items:
        cat = item.get("category", "ai")
        limit = category_limits.get(cat, 5)
        if used.get(cat, 0) >= limit:
            continue
        trimmed.append(item)
        used[cat] = used.get(cat, 0) + 1
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

    brief["date"] = run_now.strftime("%Y-%m-%d")
    brief["updated_at"] = run_now.strftime("%Y-%m-%d %H:%M")
    dump_json(STATE_DIR / "brief.json", brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

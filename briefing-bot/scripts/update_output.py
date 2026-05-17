from __future__ import annotations

import re

from common import OUTPUT_FILE, OUTPUT_TITLE, STATE_DIR, load_json, now_cst


def bullet_entries(entries: list[dict]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()
        source = entry.get("source", "").strip()
        url = entry.get("url", "").strip()
        if not title:
            continue
        line = f"- [{title}]({url})" if url else f"- {title}"
        if summary:
            line += f"：{summary}"
        if source:
            line += f"（{source}）"
        lines.append(line)
    return lines or ["- 暂无。"]


def bullet_text(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] or ["- 暂无。"]


def render_block(brief: dict) -> str:
    date = brief["date"]
    updated = brief["updated_at"]
    sections = [
        f"## {date}",
        "",
        f"_更新时间：{updated}_",
        "",
        "### 今日判断",
        brief.get("today_take", "暂无。"),
        "",
        "### Agent Watch",
        *bullet_entries(brief.get("agent_watch", [])),
        "",
        "### Model Watch",
        *bullet_entries(brief.get("model_watch", [])),
        "",
        "### Design x AI",
        *bullet_entries(brief.get("design_ai", [])),
        "",
        "### 快速雷达",
        *bullet_entries(brief.get("quick_radar", [])),
        "",
        "### 值得跟进",
        *bullet_text(brief.get("follow_up", [])),
        "",
        "### 来源参考",
        *bullet_text(brief.get("sources_used", [])),
        "",
    ]
    return "\n".join(sections)


def default_document() -> str:
    return (
        f"# {OUTPUT_TITLE}\n\n"
        "这个文件只保留一个，按日期倒序追加每日 AI 资讯整理。\n\n"
    )


def update_output_file(block: str, date: str) -> None:
    if OUTPUT_FILE.exists():
        text = OUTPUT_FILE.read_text(encoding="utf-8")
    else:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        text = default_document()

    pattern = re.compile(rf"^## {re.escape(date)}\n.*?(?=^## |\Z)", re.S | re.M)
    if pattern.search(text):
        new_text = pattern.sub(block, text, count=1)
    else:
        parts = text.split("\n\n", 2)
        if len(parts) >= 3:
            header, intro, remainder = parts
            new_text = f"{header}\n\n{intro}\n\n{block}{remainder}"
        else:
            new_text = text.rstrip() + "\n\n" + block
    OUTPUT_FILE.write_text(new_text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    brief = load_json(STATE_DIR / "brief.json", {})
    date = brief.get("date") or now_cst().strftime("%Y-%m-%d")
    update_output_file(render_block(brief), date)
    print(date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

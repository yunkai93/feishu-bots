from __future__ import annotations

import re

from common import OUTPUT_TITLE, OUTPUT_WEB_URL, RENDERED_OUTPUT_FILE, STATE_DIR, load_json, now_cst


def load_brief() -> dict:
    return load_json(STATE_DIR / "brief.json", {})


def latest_date(brief: dict | None = None) -> str:
    data = brief or load_brief()
    return data.get("date") or now_cst().strftime("%Y-%m-%d")


def latest_news_block(date: str | None = None) -> str:
    target_date = date or latest_date()
    if not RENDERED_OUTPUT_FILE.exists():
        return f"{target_date} 的 {OUTPUT_TITLE} 还没有生成。"
    text = RENDERED_OUTPUT_FILE.read_text(encoding="utf-8")
    marker = f"## {target_date}\n"
    start = text.find(marker)
    if start == -1:
        return f"{target_date} 的 {OUTPUT_TITLE} 还没有生成。"
    next_pos = text.find("\n## ", start + len(marker))
    block = text[start: next_pos if next_pos != -1 else len(text)].strip()
    return block.replace("](", " | ").replace("[", "").replace(")", "")


def entry_line(entry: dict) -> str:
    title = (entry.get("title") or "").strip()
    summary = (entry.get("summary") or "").strip()
    source = (entry.get("source") or "").strip()
    url = (entry.get("url") or "").strip()
    if not title:
        return ""
    text = f"- {title}"
    if summary:
        text += f"：{summary}"
    if source:
        text += f"（{source}）"
    if url:
        text += f"\n  {url}"
    return text


def compact_digest(brief: dict | None = None) -> str:
    data = brief or load_brief()
    date = latest_date(data)
    updated = data.get("updated_at", "")
    lines = [
        f"{OUTPUT_TITLE} {date}",
        f"更新时间：{updated}" if updated else "",
        "",
        f"今日判断：{data.get('today_take', '暂无。')}",
        "",
    ]
    section_map = [
        ("智能体动态", data.get("agent_watch", []), 5),
        ("模型动态", data.get("model_watch", []), 4),
        ("设计师工作流", data.get("design_ai", []), 5),
        ("快速雷达", data.get("quick_radar", []), 4),
    ]
    for title, entries, limit in section_map:
        if not entries:
            continue
        lines.append(f"[{title}]")
        for entry in entries[:limit]:
            rendered = entry_line(entry)
            if rendered:
                lines.append(rendered)
        lines.append("")
    follow_up = data.get("follow_up", [])
    if follow_up:
        lines.append("[值得跟进]")
        for item in follow_up[:4]:
            lines.append(f"- {item}")
        lines.append("")
    sources = data.get("sources_used", [])
    if sources:
        lines.append("来源：" + " / ".join(sources))
    return "\n".join(line for line in lines if line is not None).strip()


def help_text() -> str:
    return "\n".join(
        [
            "群里可用指令：",
            "1. @我 帮助",
            "2. @我 重跑早报",
            "",
            "私聊我时：",
            "- 直接发问题即可",
            "- 仅提供纯问答，不执行服务器操作",
        ]
    )


def sources_text(brief: dict | None = None) -> str:
    data = brief or load_brief()
    sources = data.get("sources_used", [])
    if not sources:
        return "本地还没有可用来源记录。"
    return "本次来源：\n" + "\n".join(f"- {source}" for source in sources)


def status_text(brief: dict | None = None, chat_id: str = "") -> str:
    data = brief or load_brief()
    parts = [
        f"日期：{latest_date(data)}",
        f"更新时间：{data.get('updated_at', '未知')}",
        f"智能体条数：{len(data.get('agent_watch', []))}",
        f"模型条数：{len(data.get('model_watch', []))}",
        f"设计条数：{len(data.get('design_ai', []))}",
        f"雷达条数：{len(data.get('quick_radar', []))}",
        f"群ID：{'已记录' if chat_id else '未记录'}",
    ]
    return "\n".join(parts)


def normalize_command(text: str) -> str:
    cleaned = re.sub(r"@_user_\d+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.lower()


def latest_take(brief: dict | None = None) -> str:
    data = brief or load_brief()
    return f"{latest_date(data)}\n{data.get('today_take', '暂无。')}"


def full_brief_text(brief: dict | None = None) -> str:
    data = brief or load_brief()
    return latest_news_block(latest_date(data))[:3500]


def _card_line(title: str, summary: str, url: str = "") -> str:
    head = title.strip()
    body = summary.strip()
    line = f"• **{head}**"
    if body:
        line += f"\n{body}"
    if url:
        line += f"\n[查看原文]({url})"
    return line


def build_brief_card(brief: dict | None = None) -> dict:
    data = brief or load_brief()
    date = latest_date(data)
    updated = data.get("updated_at", "")
    elements: list[dict] = [
        {
            "tag": "markdown",
            "content": f"<font color='grey'>每日 AI / 智能体 / 设计协作资讯</font>",
        },
        {
            "tag": "markdown",
            "content": f"**{OUTPUT_TITLE} {date}**\n更新时间：{updated}" if updated else f"**{OUTPUT_TITLE} {date}**",
        },
        {
            "tag": "hr",
        },
        {
            "tag": "markdown",
            "content": f"**今日判断**\n{data.get('today_take', '暂无。')}",
        },
    ]

    section_map = [
        ("智能体动态", data.get("agent_watch", []), 5),
        ("模型动态", data.get("model_watch", []), 4),
        ("设计师工作流", data.get("design_ai", []), 5),
        ("快速雷达", data.get("quick_radar", []), 4),
    ]
    for title, entries, limit in section_map:
        if not entries:
            continue
        lines = [_card_line(entry.get("title", ""), entry.get("summary", ""), entry.get("url", "")) for entry in entries[:limit]]
        lines = [line for line in lines if line.strip()]
        if not lines:
            continue
        elements.extend(
            [
                {"tag": "hr"},
                {"tag": "markdown", "content": f"**{title}**"},
                {"tag": "markdown", "content": "\n\n".join(lines)},
            ]
        )

    follow_up = data.get("follow_up", [])
    if follow_up:
        elements.extend(
            [
                {"tag": "hr"},
                {"tag": "markdown", "content": "**值得跟进**"},
                {"tag": "markdown", "content": "\n".join(f"• {item}" for item in follow_up[:4])},
            ]
        )

    sources = data.get("sources_used", [])
    if sources:
        elements.extend(
            [
                {"tag": "hr"},
                {"tag": "markdown", "content": "来源：" + " / ".join(sources)},
            ]
        )
    if OUTPUT_WEB_URL:
        elements.extend(
            [
                {"tag": "hr"},
                {"tag": "markdown", "content": f"[查看完整归档]({OUTPUT_WEB_URL})"},
            ]
        )

    return {
        "config": {"wide_screen_mode": True, "enable_forward": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"{OUTPUT_TITLE} {date}",
            },
            "template": "turquoise",
        },
        "elements": elements,
    }

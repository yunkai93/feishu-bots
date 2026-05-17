from __future__ import annotations

import json
import subprocess
from pathlib import Path

from common import CHAT_STATE_DIR, P2P_LOG_DIR, SANDBOX_DIR, ensure_dirs, now_cst


MAX_TURNS = 24
SUMMARY_TRIGGER = 18
SUMMARY_KEEP_TAIL = 8

SYSTEM_PROMPT = (
    "你现在是一个纯问答聊天机器人。"
    "禁止调用任何工具，禁止访问文件，禁止执行命令，禁止联网，禁止提供服务器控制能力。"
    "不能假装看过本地文件，也不能声称操作过服务器。"
    "回答默认使用中文，简洁、自然、准确。"
)


def session_path(user_key: str) -> Path:
    ensure_dirs()
    return CHAT_STATE_DIR / f"{user_key}.json"


def log_path(user_key: str) -> Path:
    ensure_dirs()
    return P2P_LOG_DIR / f"{user_key}.log"


def load_session(user_key: str) -> dict:
    path = session_path(user_key)
    if not path.exists():
        return {"summary": "", "messages": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(user_key: str, data: dict) -> None:
    session_path(user_key).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_log(user_key: str, role: str, text: str) -> None:
    path = log_path(user_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{now_cst().isoformat()}] {role}: {text.rstrip()}\n")


def summarize_messages(user_key: str, messages: list[dict], previous_summary: str) -> str:
    if not messages:
        return previous_summary
    ensure_dirs()
    out_file = SANDBOX_DIR / f"{user_key}_summary.txt"
    transcript = []
    if previous_summary:
        transcript.append(f"已有摘要：\n{previous_summary}\n")
    for msg in messages:
        transcript.append(f"{msg['role']}: {msg['content']}")
    prompt = (
        "请把下面的用户与助手对话压缩成长期上下文摘要。"
        "保留：用户偏好、已讨论主题、未完成问题、术语约定、重要事实。"
        "不要写废话，不要复述每一轮原文。输出中文纯文本。\n\n"
        + "\n".join(transcript)
    )
    cmd = [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(SANDBOX_DIR),
        "-s",
        "read-only",
        "-o",
        str(out_file),
        prompt,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        return previous_summary
    return out_file.read_text(encoding="utf-8").strip()[:4000]


def maybe_compact_session(user_key: str, session: dict) -> dict:
    messages = session.get("messages", [])
    if len(messages) < SUMMARY_TRIGGER:
        return session
    keep_tail = messages[-SUMMARY_KEEP_TAIL:]
    to_summarize = messages[:-SUMMARY_KEEP_TAIL]
    session["summary"] = summarize_messages(user_key, to_summarize, session.get("summary", ""))
    session["messages"] = keep_tail
    save_session(user_key, session)
    return session


def build_prompt(session: dict, question: str) -> str:
    parts: list[str] = [SYSTEM_PROMPT]
    summary = session.get("summary", "").strip()
    if summary:
        parts.append("以下是该用户历史对话摘要：\n" + summary)
    messages = session.get("messages", [])
    if messages:
        parts.append("以下是最近对话：")
        for msg in messages[-MAX_TURNS:]:
            parts.append(f"{msg['role']}: {msg['content']}")
    parts.append(f"用户: {question}")
    parts.append("请直接回复用户，不要解释你的限制。")
    return "\n\n".join(parts)


def ask(user_key: str, question: str) -> str:
    ensure_dirs()
    out_file = SANDBOX_DIR / f"{user_key}_last_answer.txt"
    session = maybe_compact_session(user_key, load_session(user_key))
    prompt = build_prompt(session, question)
    cmd = [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(SANDBOX_DIR),
        "-s",
        "read-only",
        "-o",
        str(out_file),
        prompt,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "chat agent failed")
    answer = out_file.read_text(encoding="utf-8").strip()
    if not answer:
        return "这次没有生成可用回复，请稍后再试。"

    session.setdefault("messages", [])
    session["messages"].append({"role": "user", "content": question})
    session["messages"].append({"role": "assistant", "content": answer})
    save_session(user_key, session)
    append_log(user_key, "user", question)
    append_log(user_key, "assistant", answer)
    return answer[:3500]


def ask_safe(user_key: str, question: str) -> str:
    try:
        return ask(user_key, question)
    except Exception:
        append_log(user_key, "system", "chat agent failed")
        return "当前问答服务暂时不可用，请稍后再试。"

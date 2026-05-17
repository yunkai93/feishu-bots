from __future__ import annotations

import json
import subprocess
import threading
import traceback

import lark_oapi as lark
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from chat_agent import ask_safe
from common import BRIEFING_RUN_SCRIPT, LOG_DIR, REPO_PYTHON, ensure_dirs, env, now_cst, set_env_values
from shared.feishu import build_client, reply_text, send_text_to_chat


LOG_FILE = LOG_DIR / "feishu-reply.log"


def log_line(text: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(text.rstrip() + "\n")


def extract_text(content: str) -> str:
    try:
        payload = json.loads(content)
    except Exception:
        return ""
    return (payload.get("text") or "").strip()


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


def rerun_briefing() -> str:
    cmd = [str(REPO_PYTHON), str(BRIEFING_RUN_SCRIPT)]
    proc = subprocess.run(cmd, cwd=str(BRIEFING_RUN_SCRIPT.parent.parent), text=True, capture_output=True)
    if proc.returncode != 0:
        log_line(proc.stderr or proc.stdout)
        return "重跑失败，请稍后查看服务器日志。"
    return "早报已重跑，最新卡片已推送到群里。"


def handle_group_message(message_id: str, user_text: str) -> None:
    command = normalize_command(user_text)
    if any(key in command for key in ["帮助", "help", "指令", "命令"]):
        reply_text(message_id, help_text())
        log_line(f"{now_cst().isoformat()} replied group help: {message_id}")
        return
    if "重跑" in command and "早报" in command:
        reply_text(message_id, rerun_briefing())
        log_line(f"{now_cst().isoformat()} replied group rerun: {message_id}")
        return
    reply_text(message_id, help_text())
    log_line(f"{now_cst().isoformat()} replied group fallback: {message_id}")


def normalize_command(text: str) -> str:
    import re

    cleaned = re.sub(r"@_user_\d+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.lower()


def user_key_from_event(data: P2ImMessageReceiveV1) -> str:
    sender = data.event.sender.sender_id if data.event and data.event.sender else None
    if sender is None:
        return "unknown"
    return sender.open_id or sender.user_id or sender.union_id or "unknown"


def handle_p2p_message(user_key: str, chat_id: str, message_id: str, user_text: str) -> None:
    answer = ask_safe(user_key, user_text)
    send_text_to_chat(chat_id, answer)
    log_line(f"{now_cst().isoformat()} replied p2p: {message_id} user={user_key}")


def dispatch_async(target, *args) -> None:
    def runner() -> None:
        try:
            target(*args)
        except Exception as exc:
            log_line(f"{now_cst().isoformat()} async error: {exc}")
            log_line(traceback.format_exc())

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    if data.event is None or data.event.message is None:
        return
    if data.event.sender and data.event.sender.sender_type == "bot":
        return
    if data.event.message.chat_type == "group" and data.event.message.chat_id:
        if not env("FEISHU_CHAT_ID"):
            set_env_values({"FEISHU_CHAT_ID": data.event.message.chat_id})
    if data.event.message.message_type != "text":
        reply_text(data.event.message.message_id, "请发送文本消息。")
        return
    user_text = extract_text(data.event.message.content or "")
    if not user_text:
        reply_text(data.event.message.message_id, "消息解析失败，请发送文本消息。")
        return
    if data.event.message.chat_type == "p2p":
        dispatch_async(
            handle_p2p_message,
            user_key_from_event(data),
            data.event.message.chat_id,
            data.event.message.message_id,
            user_text,
        )
    else:
        dispatch_async(handle_group_message, data.event.message.message_id, user_text)
    log_line(f"{now_cst().isoformat()} accepted {data.event.message.message_id}: {user_text}")


event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)


def main() -> int:
    ensure_dirs()
    build_client()
    cli = lark.ws.Client(
        env("FEISHU_APP_ID"),
        env("FEISHU_APP_SECRET"),
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    cli.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

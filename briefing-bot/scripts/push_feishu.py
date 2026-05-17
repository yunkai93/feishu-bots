from __future__ import annotations

from briefing_view import build_brief_card, load_brief
from common import env
from shared.feishu import enabled, send_card_to_chat


def main() -> int:
    if not enabled():
        return 0
    chat_id = env("FEISHU_CHAT_ID")
    if not chat_id:
        return 0

    send_card_to_chat(chat_id, build_brief_card(load_brief()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

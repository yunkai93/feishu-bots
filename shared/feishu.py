from __future__ import annotations

import json

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from shared.runtime import env, new_uuid, require_env


def enabled() -> bool:
    return bool(env("FEISHU_APP_ID") and env("FEISHU_APP_SECRET"))


def build_client() -> lark.Client:
    return (
        lark.Client.builder()
        .app_id(require_env("FEISHU_APP_ID"))
        .app_secret(require_env("FEISHU_APP_SECRET"))
        .build()
    )


def text_content(text: str) -> str:
    return json.dumps({"text": text}, ensure_ascii=False)


def send_message_to_chat(chat_id: str, msg_type: str, content: str) -> dict:
    client = build_client()
    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type(msg_type)
            .content(content)
            .uuid(new_uuid())
            .build()
        )
        .build()
    )
    response = client.im.v1.message.create(request)
    if not response.success():
        raise SystemExit(
            f"feishu send failed, code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
        )
    return json.loads(lark.JSON.marshal(response.data, indent=2))


def send_text_to_chat(chat_id: str, text: str) -> dict:
    return send_message_to_chat(chat_id, "text", text_content(text))


def send_card_to_chat(chat_id: str, card: dict) -> dict:
    return send_message_to_chat(chat_id, "interactive", json.dumps(card, ensure_ascii=False))


def reply_text(message_id: str, text: str) -> dict:
    client = build_client()
    request = (
        ReplyMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            ReplyMessageRequestBody.builder()
            .msg_type("text")
            .content(text_content(text))
            .build()
        )
        .build()
    )
    response = client.im.v1.message.reply(request)
    if not response.success():
        raise SystemExit(
            f"feishu reply failed, code={response.code}, msg={response.msg}, log_id={response.get_log_id()}"
        )
    return json.loads(lark.JSON.marshal(response.data, indent=2))

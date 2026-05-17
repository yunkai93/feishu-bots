from __future__ import annotations

from common import env


def main() -> int:
    keys = [
        "FEISHU_APP_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_CHAT_ID",
    ]
    for key in keys:
        value = env(key)
        print(f"{key}={'SET' if value else 'MISSING'}")
    print("还需要在飞书开放平台为应用开启：机器人能力、发送消息权限、接收消息事件权限。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.runtime import set_env_values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-secret", required=True)
    parser.add_argument("--chat-id", default="")
    args = parser.parse_args()

    updates = {
        "FEISHU_APP_ID": args.app_id.strip(),
        "FEISHU_APP_SECRET": args.app_secret.strip(),
    }
    if args.chat_id.strip():
        updates["FEISHU_CHAT_ID"] = args.chat_id.strip()
    set_env_values(updates)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

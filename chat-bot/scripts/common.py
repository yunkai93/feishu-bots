from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.runtime import ensure_dir, env, load_json, now_cst, path_env, set_env_values


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PRODUCT_ROOT / "state"
LOG_DIR = PRODUCT_ROOT / "logs"
CHAT_STATE_DIR = STATE_DIR / "sessions"
P2P_LOG_DIR = LOG_DIR / "p2p"
SANDBOX_DIR = path_env("CHAT_BOT_SANDBOX_DIR", Path("/tmp/feishu-bots-chat"))
BRIEFING_RUN_SCRIPT = REPO_ROOT / "briefing-bot" / "scripts" / "run_briefing.py"
REPO_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


def ensure_dirs() -> None:
    ensure_dir(STATE_DIR)
    ensure_dir(LOG_DIR)
    ensure_dir(CHAT_STATE_DIR)
    ensure_dir(P2P_LOG_DIR)
    ensure_dir(SANDBOX_DIR)

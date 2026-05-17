from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.runtime import dump_json, ensure_dir, env, load_json, now_cst, path_env


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PRODUCT_ROOT / "config" / "sources.json"
PROMPT_FILE = PRODUCT_ROOT / "prompts" / "brief_prompt.md"
SCHEMA_FILE = PRODUCT_ROOT / "prompts" / "brief_schema.json"
STATE_DIR = PRODUCT_ROOT / "state"
LOG_DIR = PRODUCT_ROOT / "logs"
TMP_DIR = PRODUCT_ROOT / "tmp"

DEFAULT_OUTPUT_REPO = REPO_ROOT
OUTPUT_REPO_PATH = path_env("BRIEFING_OUTPUT_REPO_PATH", DEFAULT_OUTPUT_REPO)
OUTPUT_FILE_PATH = env("BRIEFING_OUTPUT_FILE_PATH", "outputs/AI Briefing.md")
OUTPUT_FILE = OUTPUT_REPO_PATH / OUTPUT_FILE_PATH
OUTPUT_TITLE = env("BRIEFING_OUTPUT_TITLE", "AI早报")
OUTPUT_WEB_URL = env("BRIEFING_OUTPUT_WEB_URL")
PUBLISH_REMOTE = env("BRIEFING_PUBLISH_REMOTE", "origin")
PUBLISH_BRANCH = env("BRIEFING_PUBLISH_BRANCH", "main")


def ensure_dirs() -> None:
    ensure_dir(STATE_DIR)
    ensure_dir(LOG_DIR)
    ensure_dir(TMP_DIR)


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

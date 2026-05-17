from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / ".env"
VENV_DIR = REPO_ROOT / ".venv"


def now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def bool_env(name: str, default: bool = False) -> bool:
    raw = env(name)
    if not raw:
        return default
    return raw.lower() not in {"0", "false", "no", "off"}


def require_env(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"missing required env: {name}")
    return value


def path_env(name: str, default: Path) -> Path:
    raw = env(name)
    if not raw:
        return default
    return Path(raw).expanduser()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def new_uuid() -> str:
    return str(uuid.uuid4())


def load_env_file() -> None:
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            os.environ.setdefault(key, value)


def set_env_values(updates: dict[str, str]) -> None:
    existing: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = raw_line.split("=", 1)
            existing[key.strip()] = value.strip()
    existing.update({key: value for key, value in updates.items() if value is not None})
    rendered = [f"{key}={value}" for key, value in sorted(existing.items())]
    ENV_FILE.write_text("\n".join(rendered) + "\n", encoding="utf-8")
    try:
        ENV_FILE.chmod(0o600)
    except Exception:
        pass
    for key, value in updates.items():
        os.environ[key] = value


load_env_file()

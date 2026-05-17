#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$REPO_ROOT/.venv"

python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r "$REPO_ROOT/requirements.txt"

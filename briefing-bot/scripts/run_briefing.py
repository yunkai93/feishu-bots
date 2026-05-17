from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from common import OUTPUT_FILE_PATH, OUTPUT_REMOTE_URL, PRODUCT_ROOT, PUBLISH_BRANCH, PUBLISH_REMOTE, RENDERED_OUTPUT_FILE, TMP_DIR, ensure_dirs, now_cst
from shared.runtime import bool_env


SCRIPTS = [
    "fetch_sources.py",
    "generate_brief.py",
    "update_output.py",
]


def run_cmd(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=check)


def run_step(script: str) -> None:
    path = PRODUCT_ROOT / "scripts" / script
    proc = run_cmd([sys.executable, str(path)], cwd=PRODUCT_ROOT, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"{script} failed:\n{proc.stderr or proc.stdout}")


def git_publish() -> None:
    if not bool_env("BRIEFING_GIT_PUSH", True):
        return
    origin = OUTPUT_REMOTE_URL.strip()
    if not origin:
        raise SystemExit("git publish failed: BRIEFING_OUTPUT_REMOTE_URL not set")

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="briefing-publish-", dir=str(TMP_DIR)) as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        run_cmd(
            ["git", "clone", "--origin", PUBLISH_REMOTE, "--depth", "1", "--branch", PUBLISH_BRANCH, origin, str(repo_dir)],
            cwd=PRODUCT_ROOT,
        )

        if not RENDERED_OUTPUT_FILE.exists():
            raise SystemExit(f"git publish failed: rendered output not found: {RENDERED_OUTPUT_FILE}")
        target_file = repo_dir / OUTPUT_FILE_PATH
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(RENDERED_OUTPUT_FILE.read_text(encoding="utf-8"), encoding="utf-8")

        run_cmd(["git", "add", OUTPUT_FILE_PATH], cwd=repo_dir)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(repo_dir))
        if diff.returncode == 0:
            return
        msg = f"chore: update briefing {now_cst().strftime('%Y-%m-%d')}"
        run_cmd(["git", "commit", "-m", msg], cwd=repo_dir)
        run_cmd(["git", "push", PUBLISH_REMOTE, PUBLISH_BRANCH], cwd=repo_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-git", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    for script in SCRIPTS:
        run_step(script)
    if not args.no_git:
        git_publish()
    run_step("push_feishu.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

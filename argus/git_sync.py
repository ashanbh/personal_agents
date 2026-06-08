#!/usr/bin/env python3
"""
git_sync.py — safely commit and push ONE subfolder of a git repo.

Built for unattended / agent use. It deliberately NEVER runs `git add -A`: it
stages and commits only the path you name, so sibling projects and secrets that
live in the same repo are never swept into the commit. It clears a stale
index.lock, skips committing when there's nothing to commit, then pushes.

Usage (CLI):
  poetry run python git_sync.py PATH -m "message"
  poetry run python git_sync.py ~/PROJ/ASHANBH/personal_agents/focus_coach_native \\
      -m "focus_coach_native: progress" --remote origin --branch main
  poetry run python git_sync.py PATH -m "msg" --no-push        # commit only
  poetry run python git_sync.py PATH -m "msg" --notify         # Slack the result

Importable:
  from git_sync import commit_push
  res = commit_push("~/PROJ/.../focus_coach_native", "msg")

Auth: pushing uses your existing git credentials (SSH key / credential helper).
It fails with a clear message if none are available (e.g. inside a sandbox with
no key) — that's expected; run it on the machine where your key lives.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)


def _repo_root(path: Path) -> Path:
    r = _run(["git", "rev-parse", "--show-toplevel"], cwd=path)
    if r.returncode != 0:
        raise RuntimeError(f"{path} is not inside a git repo: {r.stderr.strip()}")
    return Path(r.stdout.strip())


def commit_push(
    subpath: str | os.PathLike,
    message: str,
    remote: str = "origin",
    branch: str | None = None,
    push: bool = True,
) -> dict:
    """Stage+commit+push only `subpath`. Returns a result dict; raises on error."""
    subpath = Path(os.path.expanduser(str(subpath))).resolve()
    if not subpath.exists():
        raise FileNotFoundError(f"path does not exist: {subpath}")

    anchor = subpath if subpath.is_dir() else subpath.parent
    root = _repo_root(anchor)
    try:
        rel = subpath.relative_to(root)
    except ValueError:
        raise RuntimeError(f"{subpath} is not inside repo root {root}")

    result: dict = {"root": str(root), "subpath": str(rel),
                    "committed": False, "pushed": False}

    # Clear a stale lock (owner-only; a no-op if absent).
    lock = root / ".git" / "index.lock"
    if lock.exists():
        try:
            lock.unlink()
        except OSError as e:
            result["lock_warning"] = f"could not remove index.lock: {e}"

    # Stage ONLY the named subpath.
    r = _run(["git", "add", "--", str(rel)], cwd=root)
    if r.returncode != 0:
        raise RuntimeError(f"git add failed: {r.stderr.strip()}")

    # Anything staged under this path?
    staged = _run(["git", "diff", "--cached", "--name-only", "--", str(rel)], cwd=root)
    if not staged.stdout.strip():
        result["note"] = "nothing to commit"
        return result

    # Commit, scoped to the subpath so unrelated staged changes are untouched.
    r = _run(["git", "commit", "-m", message, "--", str(rel)], cwd=root)
    if r.returncode != 0:
        raise RuntimeError(f"git commit failed: {(r.stderr or r.stdout).strip()}")
    result["committed"] = True
    result["commit"] = _run(["git", "rev-parse", "--short", "HEAD"], cwd=root).stdout.strip()

    if not push:
        return result

    if branch is None:
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root).stdout.strip()
    result["branch"] = branch
    r = _run(["git", "push", remote, branch], cwd=root)
    if r.returncode != 0:
        raise RuntimeError(
            f"git push failed (auth/network — is your SSH key available here?): "
            f"{r.stderr.strip()}")
    result["pushed"] = True
    return result


def _notify(text: str) -> None:
    """Best-effort Slack ping via the sibling notifier."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from notify_via_slack import send_slack
        send_slack(text)
    except Exception as e:
        print(f"(notify skipped: {e})", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely commit+push one subfolder of a git repo.")
    ap.add_argument("path", help="Subfolder to commit (must be inside a git repo).")
    ap.add_argument("-m", "--message", required=True, help="Commit message.")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default=None, help="Defaults to the current branch.")
    ap.add_argument("--no-push", action="store_true", help="Commit only, don't push.")
    ap.add_argument("--notify", action="store_true", help="Slack the result via argus.")
    args = ap.parse_args()

    try:
        res = commit_push(args.path, args.message, remote=args.remote,
                          branch=args.branch, push=not args.no_push)
    except Exception as e:
        msg = f"git_sync FAILED for {args.path}: {e}"
        print(msg, file=sys.stderr)
        if args.notify:
            _notify(f"❌ {msg}")
        return 1

    if res.get("note") == "nothing to commit":
        print("Nothing to commit.")
        return 0
    summary = (f"committed {res.get('commit','?')} "
               + ("and pushed " if res.get("pushed") else "(not pushed) ")
               + f"[{res['subpath']} -> {res.get('branch','?')}]")
    print(summary)
    if args.notify:
        _notify(f"✅ git_sync: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

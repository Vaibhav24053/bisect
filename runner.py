#!/usr/bin/env python3
"""Bisect step 1: run the test command on every commit and report pass/fail.

Usage (from your bisect-project folder, venv active):
    python3 runner.py sample-repo
    python3 runner.py sample-repo --good <hash> --bad HEAD --workers 1

Each commit is checked out into its own temporary git worktree, so runs are
isolated (and can safely run in parallel later with --workers N).
"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

GIT_LOCK = threading.Lock()  # git worktree add/remove must not run at once


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


def list_commits(repo, good, bad):
    """Oldest -> newest, including `good` itself."""
    between = git(repo, "rev-list", "--reverse", "%s..%s" % (good, bad)).split()
    return [git(repo, "rev-parse", good)] + between


def run_one(repo, commit, test_cmd, timeout):
    """Run the tests on one commit. Returns a result dict."""
    start = time.time()
    work = tempfile.mkdtemp(prefix="bisect-")
    wt = os.path.join(work, "wt")
    try:
        with GIT_LOCK:
            git(repo, "worktree", "add", "--detach", "-q", wt, commit)
        cmd = shlex.split(test_cmd)
        if cmd[0] in ("python", "python3"):
            cmd[0] = sys.executable
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        try:
            p = subprocess.run(cmd, cwd=wt, capture_output=True, text=True,
                               timeout=timeout, env=env)
            code, out = p.returncode, (p.stdout + p.stderr)
        except subprocess.TimeoutExpired:
            code, out = 124, "timed out after %ss" % timeout
        status = "pass" if code == 0 else ("fail" if code == 1 else "error")
        return {"commit": commit, "status": status, "code": code,
                "output": out, "secs": time.time() - start}
    finally:
        with GIT_LOCK:
            subprocess.run(["git", "worktree", "remove", "--force", wt],
                           cwd=repo, capture_output=True)
        shutil.rmtree(work, ignore_errors=True)


def find_culprit(commits, results):
    """First commit that fails right after a passing one."""
    for prev, cur in zip(commits, commits[1:]):
        if results[prev]["status"] == "pass" and results[cur]["status"] == "fail":
            return cur
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--good", help="known-good commit (default: first commit)")
    ap.add_argument("--bad", default="HEAD", help="known-bad commit (default: HEAD)")
    ap.add_argument("--cmd", default="python -m pytest -q -x -p no:cacheprovider",
                    help="test command; exit 0 = pass, 1 = fail, other = error")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=120)
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    good = a.good or git(repo, "rev-list", "--max-parents=0", a.bad)
    commits = list_commits(repo, good, a.bad)
    print("Testing %d commits with %d worker(s)...\n" % (len(commits), a.workers))

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        out = list(ex.map(lambda c: run_one(repo, c, a.cmd, a.timeout), commits))
    results = {r["commit"]: r for r in out}

    icon = {"pass": "PASS", "fail": "FAIL", "error": "ERR "}
    for c in commits:
        r = results[c]
        msg = git(repo, "log", "-1", "--format=%s", c)
        print("%s  %s  %s  (%.2fs)" % (icon[r["status"]], c[:8], msg, r["secs"]))

    print("\nTotal time: %.1fs" % (time.time() - t0))
    culprit = find_culprit(commits, results)
    if culprit:
        print("\nFirst bad commit: %s" % git(repo, "log", "-1", "--format=%h  %s", culprit))
    else:
        print("\nNo clean pass->fail transition found.")


if __name__ == "__main__":
    main()

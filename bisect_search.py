#!/usr/bin/env python3
"""Bisect step 2: parallel k-section search for the first bad commit.

Instead of testing all commits (or one at a time like `git bisect`), each
round tests up to --workers commits spread across the remaining range, in
parallel, then keeps only the slice that contains the pass->fail switch.

Usage (from bisect-project, venv active):
    python3 bisect_search.py sample-repo
    SIM_BUILD_SECS=3 python3 bisect_search.py sample-repo --workers 8
"""
import argparse
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor

from runner import git, list_commits, run_one

DEFAULT_CMD = "python -m pytest -q -x -p no:cacheprovider"


def pick_probes(good, bad, k):
    """Up to k indices strictly between good and bad, evenly spread."""
    gap = bad - good - 1
    k = min(k, gap)
    probes = {good + round((i + 1) * (bad - good) / (k + 1)) for i in range(k)}
    return sorted(p for p in probes if good < p < bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--good")
    ap.add_argument("--bad", default="HEAD")
    ap.add_argument("--cmd", default=DEFAULT_CMD)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    good_hash = a.good or git(repo, "rev-list", "--max-parents=0", a.bad)
    commits = list_commits(repo, good_hash, a.bad)
    n = len(commits)
    good, bad = 0, n - 1          # assumed: first passes, last fails
    print("Searching %d commits (%d workers)\n" % (n, a.workers))

    runs, rounds, run_secs = 0, 0, []
    t0 = time.time()
    while bad - good > 1:
        probes = pick_probes(good, bad, a.workers)
        r0 = time.time()
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            res = list(ex.map(lambda i: run_one(repo, commits[i], a.cmd, a.timeout), probes))
        rounds += 1
        runs += len(probes)
        run_secs += [r["secs"] for r in res]

        new_good, new_bad, seen_fail = good, bad, False
        for i, r in zip(probes, res):
            if r["status"] == "error":
                print("  warning: commit %s errored (code %s); ignoring it" % (commits[i][:8], r["code"]))
            elif r["status"] == "pass":
                if seen_fail:
                    print("  warning: pass after a fail at %s - history not monotonic" % commits[i][:8])
                else:
                    new_good = i
            elif not seen_fail:
                seen_fail, new_bad = True, i
        line = " ".join("%s=%s" % (commits[i][:7], r["status"].upper()[:4]) for i, r in zip(probes, res))
        print("Round %d (%.1fs): %s" % (rounds, time.time() - r0, line))
        print("          range now %d commits\n" % (new_bad - new_good + 1))
        if (new_good, new_bad) == (good, bad):
            raise SystemExit("No progress (all probes errored?). Aborting.")
        good, bad = new_good, new_bad

    total = time.time() - t0
    avg = sum(run_secs) / len(run_secs)
    print("First bad commit: %s" % git(repo, "log", "-1", "--format=%h  %s", commits[bad]))
    print("\n--- stats ---")
    print("Parallel search : %d rounds, %d test runs, %.1fs wall time" % (rounds, runs, total))
    print("Full scan       : %d runs one at a time  ~ %.0fs (estimated)" % (n, n * avg))
    steps = math.ceil(math.log2(n))
    print("git bisect      : ~%d runs one at a time ~ %.0fs (estimated)" % (steps, steps * avg))


if __name__ == "__main__":
    main()

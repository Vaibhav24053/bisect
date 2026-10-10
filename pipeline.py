#!/usr/bin/env python3
"""Bisect: find the commit that broke the tests, explain it, fix it, prove the fix.

One command:
    python3 pipeline.py sample-repo-hard
    python3 pipeline.py sample-repo-hard --compare      # also time classic git-bisect style search

Everything that happens is emitted as an event (also saved to bisect-output/events.jsonl),
so a UI can replay or stream it. Event types:
  start          commits[{index,hash,short,message}], workers
  round_start    round, probes[index...]
  probe_result   round, index, status(pass|fail|error), secs
  round_end      round, good, bad, remaining
  culprit        index, hash, short, message, diff
  baseline       runs, secs, matches        (only with --compare)
  attempt_start  n, model
  attempt_result n, model, status(pass|fail|invalid), explanation, edits, tokens, detail
  done           verified, patch, explanation, stats{...}
Environment: NEBIUS_API_KEY (required), NEBIUS_MODEL, NEBIUS_ESCALATION_MODEL, SIM_BUILD_SECS
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import diagnose as dg
from bisect_search import pick_probes
from runner import git, list_commits, run_one

SEARCH_CMD = "python -m pytest -q -x -p no:cacheprovider"


def classic_bisect(repo, commits, cmd, timeout):
    """Sequential binary search (what `git bisect run` does), measured in the same harness."""
    lo, hi, runs, t0 = 0, len(commits) - 1, 0, time.time()
    while hi - lo > 1:
        mid = (lo + hi) // 2
        r = run_one(repo, commits[mid], cmd, timeout)
        runs += 1
        lo, hi = (mid, hi) if r["status"] == "pass" else (lo, mid)
    return hi, runs, time.time() - t0


def parallel_search(repo, commits, workers, cmd, timeout, emit):
    good, bad, rounds, runs, t0 = 0, len(commits) - 1, 0, 0, time.time()
    while bad - good > 1:
        probes = pick_probes(good, bad, workers)
        rounds += 1
        emit(type="round_start", round=rounds, probes=probes)
        results = {}
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(run_one, repo, commits[i], cmd, timeout): i for i in probes}
            for f in as_completed(futs):
                i, r = futs[f], f.result()
                results[i] = r
                emit(type="probe_result", round=rounds, index=i, status=r["status"], secs=round(r["secs"], 2))
        runs += len(probes)
        new_good, new_bad, seen_fail = good, bad, False
        for i in sorted(probes):
            st = results[i]["status"]
            if st == "pass" and not seen_fail:
                new_good = i
            elif st == "fail" and not seen_fail:
                seen_fail, new_bad = True, i
        if (new_good, new_bad) == (good, bad):
            raise RuntimeError("search made no progress (did every probe error?)")
        good, bad = new_good, new_bad
        emit(type="round_end", round=rounds, good=good, bad=bad, remaining=bad - good + 1)
    return bad, {"rounds": rounds, "runs": runs, "secs": round(time.time() - t0, 2)}


def gather_files(repo, head, culprit):
    changed = [p for p in git(repo, "show", "--name-only", "--format=", culprit).split("\n") if p]
    tracked = [p for p in git(repo, "ls-tree", "-r", "--name-only", head).split("\n") if p.endswith(".py")]
    ordered = (sorted(p for p in tracked if p in changed)
               + sorted(p for p in tracked if p not in changed and not p.startswith("tests/"))
               + sorted(p for p in tracked if p not in changed and p.startswith("tests/")))
    files, budget = {}, 60000
    for p in ordered:
        text = git(repo, "show", "%s:%s" % (head, p))
        if budget - len(text) >= 0:
            files[p], budget = text, budget - len(text)
    return files


def run_pipeline(repo, out_dir="bisect-output", workers=8, attempts=3, compare=False,
                 timeout=300, client=None, on_event=None):
    repo = os.path.abspath(repo)
    os.makedirs(out_dir, exist_ok=True)
    events, T0 = [], time.time()
    jsonl = open(os.path.join(out_dir, "events.jsonl"), "w")

    def emit(**ev):
        ev["t"] = round(time.time() - T0, 2)
        events.append(ev)
        jsonl.write(json.dumps(ev) + "\n")
        jsonl.flush()
        if on_event:
            on_event(ev)

    # 1. the commit list
    first = git(repo, "rev-list", "--max-parents=0", "HEAD")
    commits = list_commits(repo, first, "HEAD")
    subjects = dict(l.split("\t", 1) for l in git(repo, "log", "--format=%H%x09%s", "HEAD").split("\n"))
    emit(type="start", workers=workers, commits=[
        {"index": i, "hash": c, "short": c[:7], "message": subjects.get(c, "")} for i, c in enumerate(commits)])

    # 2. parallel search
    bad_i, search_stats = parallel_search(repo, commits, workers, SEARCH_CMD, timeout, emit)
    culprit = commits[bad_i]
    emit(type="culprit", index=bad_i, hash=culprit, short=culprit[:7], message=subjects.get(culprit, ""),
         diff=dg.clip(git(repo, "show", "--format=", culprit), 6000))

    # 3. optional honest baseline: classic sequential binary search, same harness
    baseline = None
    if compare:
        b_i, b_runs, b_secs = classic_bisect(repo, commits, SEARCH_CMD, timeout)
        baseline = {"runs": b_runs, "secs": round(b_secs, 2)}
        emit(type="baseline", matches=(b_i == bad_i), **baseline)

    # 4. diagnose + verified fix
    head = git(repo, "rev-parse", "HEAD")
    test_out = run_one(repo, culprit, dg.TEST_CMD, timeout)["output"]   # full output, no -x
    head_files = gather_files(repo, head, culprit)
    client = client or dg.make_client()
    model = os.environ.get("NEBIUS_MODEL", dg.DEFAULT_MODEL)
    big = os.environ.get("NEBIUS_ESCALATION_MODEL")
    history, log, tokens_by_model, success = [], [], {}, None
    for n in range(1, attempts + 1):
        use = big if (big and n == attempts and n > 1) else model
        emit(type="attempt_start", n=n, model=use)
        fix = None
        try:
            fix, toks = dg.ask_model(client, use, dg.build_prompt(repo, culprit, test_out, head_files, history))
            tokens_by_model[use] = tokens_by_model.get(use, 0) + toks
            code, out, patch = dg.attempt_fix(repo, head, fix.get("edits", []), dg.TEST_CMD)
        except Exception as e:
            ex = (fix or {}).get("explanation", "(invalid proposal)")
            history.append({"n": n, "explanation": ex, "edits": (fix or {}).get("edits"), "output": str(e)})
            log.append({"n": n, "model": use, "error": str(e), "edits": (fix or {}).get("edits")})
            emit(type="attempt_result", n=n, model=use, status="invalid", explanation=ex,
                 edits=(fix or {}).get("edits"), tokens=0, detail=str(e))
            continue
        status = "pass" if code == 0 else "fail"
        log.append({"n": n, "model": use, "explanation": fix.get("explanation", ""), "edits": fix.get("edits"),
                    "exit_code": code, "test_output_tail": out[-3000:]})
        emit(type="attempt_result", n=n, model=use, status=status, explanation=fix.get("explanation", ""),
             edits=fix.get("edits"), tokens=toks, detail=dg.clip(out[-1500:], 1500))
        if code == 0:
            success = {"n": n, "model": use, "explanation": fix.get("explanation", ""), "patch": patch}
            break
        history.append({"n": n, "explanation": fix.get("explanation", ""), "edits": fix.get("edits"), "output": out})

    stats = {"search": search_stats, "baseline": baseline, "attempts": len(log),
             "tokens_by_model": tokens_by_model, "total_tokens": sum(tokens_by_model.values()),
             "total_secs": round(time.time() - T0, 2), "commits": len(commits)}
    emit(type="done", verified=bool(success), patch=(success or {}).get("patch", ""),
         explanation=(success or {}).get("explanation", ""), stats=stats)
    jsonl.close()

    # 5. artifacts
    json.dump(log, open(os.path.join(out_dir, "attempts.json"), "w"), indent=2)
    rep = ["# Bisect report", "", "- Culprit: `%s %s`" % (culprit[:7], subjects.get(culprit, "")),
           "- Commits searched: %d in %d rounds / %d test runs (%.1fs)" % (
               len(commits), search_stats["rounds"], search_stats["runs"], search_stats["secs"])]
    if baseline:
        rep.append("- Classic sequential bisect, same harness: %d runs (%.1fs)" % (baseline["runs"], baseline["secs"]))
    rep += ["- Diagnosis attempts: %d, tokens by model: %s" % (len(log), json.dumps(tokens_by_model)), ""]
    if success:
        open(os.path.join(out_dir, "fix.patch"), "w").write(success["patch"])
        rep += ["## Root cause", success["explanation"], "", "## Verified fix (model: %s)" % success["model"],
                "```diff", success["patch"], "```"]
    else:
        rep += ["## Result", "No verified fix after %d attempts." % attempts]
    open(os.path.join(out_dir, "report.md"), "w").write("\n".join(rep) + "\n")
    return events


def pretty(ev):
    t = ev["type"]
    if t == "start":
        return "Searching %d commits with %d workers..." % (len(ev["commits"]), ev["workers"])
    if t == "round_end":
        return "  round %d done: %d commits left" % (ev["round"], ev["remaining"])
    if t == "culprit":
        return "\nCulprit: %s  %s" % (ev["short"], ev["message"])
    if t == "baseline":
        return "Classic sequential bisect: %d runs, %.1fs (agrees: %s)" % (ev["runs"], ev["secs"], ev["matches"])
    if t == "attempt_start":
        return "\nAttempt %d with %s ..." % (ev["n"], ev["model"])
    if t == "attempt_result":
        return "  [%s] %s" % (ev["status"].upper(), ev["explanation"][:300] or ev["detail"][:300])
    if t == "done":
        s = ev["stats"]
        return ("\n%s  | search: %d rounds, %d runs, %.1fs | tokens: %d | total %.1fs" % (
            "FIX VERIFIED" if ev["verified"] else "NO VERIFIED FIX",
            s["search"]["rounds"], s["search"]["runs"], s["search"]["secs"], s["total_tokens"], s["total_secs"]))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--compare", action="store_true", help="also time classic sequential bisect")
    ap.add_argument("--out", default="bisect-output")
    a = ap.parse_args()
    def show(ev):
        line = pretty(ev)
        if line:
            print(line, flush=True)
    run_pipeline(a.repo, a.out, a.workers, a.attempts, a.compare, on_event=show)
    print("\nSaved to %s/: report.md, fix.patch, attempts.json, events.jsonl" % a.out)


if __name__ == "__main__":
    main()

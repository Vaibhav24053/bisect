#!/usr/bin/env python3
"""Tiny local backend for the Bisect web UI.

Wraps pipeline.run_pipeline() and streams its events to the browser live
over Server-Sent Events, so the UI shows a REAL run instead of only a
replayed events.jsonl file.

Run (from bisect-project, venv active, NEBIUS_API_KEY set):
    pip install fastapi uvicorn
    python3 server.py
Then open http://127.0.0.1:8000 in your browser.

Endpoints:
    GET /                        serves index.html (put it next to this file)
    GET /api/repos               lists runnable repo folders (an allow-list, see REPOS below)
    GET /api/run?repo=<name>     streams one pipeline run as Server-Sent Events
"""
import asyncio
import json
import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

import pipeline

HERE = Path(__file__).parent
app = FastAPI()

# Allow-list of repos the web UI may run. This is deliberate: a public demo
# must NEVER accept an arbitrary path or URL from the browser and run it,
# since that's remote code execution. Add your own generated repos here.
REPOS = {
    "sample-repo": "Easy scenario: one-line threshold bug",
    "sample-repo-hard": "Hard scenario: two bugs in one refactor commit",
}


@app.get("/")
def home():
    f = HERE / "index.html"
    if not f.exists():
        raise HTTPException(404, "index.html not found next to server.py")
    return FileResponse(f)


@app.get("/api/repos")
def list_repos():
    return [{"id": k, "label": v, "exists": (HERE / k).is_dir()} for k, v in REPOS.items()]


@app.get("/api/run")
async def run(repo: str):
    if repo not in REPOS:
        raise HTTPException(400, "unknown repo %r (see /api/repos)" % repo)
    path = HERE / repo
    if not path.is_dir():
        raise HTTPException(404, "repo folder %r does not exist on the server" % repo)
    if "NEBIUS_API_KEY" not in os.environ:
        raise HTTPException(500, "server is missing NEBIUS_API_KEY")

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    DONE = object()

    def on_event(ev):
        loop.call_soon_threadsafe(queue.put_nowait, ev)

    def worker():
        try:
            pipeline.run_pipeline(str(path), out_dir=str(path.parent / ("bisect-output-" + repo)),
                                  compare=True, on_event=on_event)
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "server_error", "error": str(e)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, DONE)

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        while True:
            ev = await queue.get()
            if ev is DONE:
                break
            yield "data: " + json.dumps(ev) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

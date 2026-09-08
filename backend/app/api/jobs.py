"""
Async job registry and SSE streaming for document ingestion pipeline.

Jobs are tracked in memory (process-lifetime). Each job emits progress
events that are both stored (for /status polling) and streamed (via SSE).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

job_router = APIRouter()

# ── Job model ─────────────────────────────────────────────────────────────────


@dataclass
class ProgressEvent:
    stage: str
    pct: int
    msg: str
    document_id: Optional[str] = None
    ts: float = field(default_factory=time.time)


@dataclass
class Job:
    job_id: str
    filename: str
    document_id: Optional[str] = None
    events: List[ProgressEvent] = field(default_factory=list)
    done: bool = False
    error: Optional[str] = None
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    _loop: Optional[object] = None

    def push(self, stage: str, pct: int, msg: str, doc_id: Optional[str] = None) -> None:
        if doc_id:
            self.document_id = doc_id
        evt = ProgressEvent(stage=stage, pct=pct, msg=msg, document_id=self.document_id)
        self.events.append(evt)
        if stage in ("done", "error"):
            self.done = True
            if stage == "error":
                self.error = msg
        try:
            if self._loop and not self._loop.is_closed():
                self._loop.call_soon_threadsafe(self._queue.put_nowait, evt)
            else:
                self._queue.put_nowait(evt)
        except Exception:
            pass

    def latest(self) -> Optional[ProgressEvent]:
        return self.events[-1] if self.events else None

    def to_status(self) -> dict:
        latest = self.latest()
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "document_id": self.document_id,
            "stage": latest.stage if latest else "queued",
            "pct": latest.pct if latest else 0,
            "msg": latest.msg if latest else "Queued...",
            "done": self.done,
            "error": self.error,
            "events": [
                {
                    "stage": e.stage,
                    "pct": e.pct,
                    "msg": e.msg,
                    "document_id": e.document_id,
                    "ts": e.ts,
                }
                for e in self.events
            ],
        }


# ── In-memory registry ────────────────────────────────────────────────────────

_jobs: Dict[str, Job] = {}


def create_job(filename: str) -> "Job":
    job_id = str(uuid.uuid4())
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    job = Job(job_id=job_id, filename=filename, _loop=loop)
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional["Job"]:
    return _jobs.get(job_id)


def list_jobs() -> List[dict]:
    return [j.to_status() for j in reversed(list(_jobs.values()))]


# ── API endpoints ─────────────────────────────────────────────────────────────


@job_router.get("/jobs")
def get_all_jobs():
    return list_jobs()


@job_router.get("/jobs/{job_id}/status")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_status()


@job_router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """SSE stream for real-time ingestion progress."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def event_generator() -> AsyncGenerator[str, None]:
        # Replay buffered events first (handles reconnect)
        for evt in list(job.events):
            payload = json.dumps({
                "stage": evt.stage,
                "pct": evt.pct,
                "msg": evt.msg,
                "document_id": evt.document_id or job.document_id,
                "ts": evt.ts,
            })
            yield f"data: {payload}\n\n"

        if job.done:
            yield 'data: {"stage": "closed"}\n\n'
            return

        while True:
            try:
                evt = await asyncio.wait_for(job._queue.get(), timeout=20.0)
                payload = json.dumps({
                    "stage": evt.stage,
                    "pct": evt.pct,
                    "msg": evt.msg,
                    "document_id": evt.document_id or job.document_id,
                    "ts": evt.ts,
                })
                yield f"data: {payload}\n\n"
                if evt.stage in ("done", "error"):
                    yield 'data: {"stage": "closed"}\n\n'
                    return
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )

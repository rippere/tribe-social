import asyncio
from datetime import datetime, timedelta
from typing import Dict
from app.models.job import Job, JobStatus

_TERMINAL_STATUSES = {JobStatus.complete, JobStatus.failed}

_store: Dict[str, Job] = {}


def get(job_id: str) -> Job | None:
    return _store.get(job_id)


def set(job: Job):
    _store[job.job_id] = job


def update(job_id: str, **kwargs):
    if job_id in _store:
        job = _store[job_id]
        for k, v in kwargs.items():
            setattr(job, k, v)


async def cleanup_loop():
    """Remove jobs older than 1 hour."""
    while True:
        await asyncio.sleep(300)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        stale = [
            jid for jid, j in _store.items()
            if j.created_at < cutoff and j.status in _TERMINAL_STATUSES
        ]
        for jid in stale:
            del _store[jid]

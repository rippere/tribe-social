import asyncio
from datetime import datetime, timedelta
from typing import Dict
from app.models.job import Job, JobStatus

# TODO(durability): This is a process-local in-memory dict. It is wiped on every
# restart, so in-flight jobs vanish and clients polling for them get a 404
# ("phantom"). Real durability requires a Supabase-backed store (jobs table +
# status/result columns) so state survives restarts and can be reconciled on
# startup. Until then, reconcile_interrupted_jobs() (below) is the minimum-viable
# stand-in: it gives clients a definitive terminal answer instead of a phantom.

_TERMINAL_STATUSES = {JobStatus.complete, JobStatus.failed}

_store: Dict[str, Job] = {}


def reconcile_interrupted_jobs() -> int:
    """Startup hook: mark any job left in a non-terminal state as failed.

    Meant to run once at process start. A job stuck mid-flight (queued/uploading/
    scoring/etc.) at startup can only be a leftover from a previous run that was
    interrupted — its background task no longer exists — so we resolve it to a
    definitive `failed` with a clear error rather than leaving a phantom that
    never completes.

    NOTE: with the current in-memory `_store`, the dict starts empty on every
    process start, so there is nothing to reconcile YET and this is effectively a
    no-op. It becomes load-bearing once a durable (Supabase-backed) store persists
    jobs across restarts — see the module TODO above. Returns the count reconciled.
    """
    reconciled = 0
    for job in _store.values():
        if job.status not in _TERMINAL_STATUSES:
            job.status = JobStatus.failed
            job.error = "interrupted by restart"
            job.message = "Failed"
            reconciled += 1
    return reconciled


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

"""
TRIBE Social Lab — FastAPI backend
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import state
from .routers import health, corpus, jobs as jobs_router, admin as admin_router
from .store.jobs import cleanup_loop, reconcile_interrupted_jobs

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load corpus on startup
    if DATA_PATH.exists():
        with open(DATA_PATH) as f:
            state.corpus_data = json.load(f)
        print(f"[startup] Loaded {len(state.corpus_data['videos'])} videos from corpus.json")
    else:
        print(f"[startup] WARNING: corpus.json not found at {DATA_PATH}")

    # Fail any job left non-terminal by a prior process (no-op with today's
    # in-memory store; load-bearing once jobs persist across restarts).
    reconciled = reconcile_interrupted_jobs()
    if reconciled:
        print(f"[startup] Marked {reconciled} interrupted job(s) as failed")

    # Start job store cleanup background task
    asyncio.create_task(cleanup_loop())

    yield
    # cleanup (nothing needed)


app = FastAPI(
    title="TRIBE Social Lab API",
    description="Neural content intelligence — corpus endpoints",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(corpus.router)
app.include_router(jobs_router.router)
app.include_router(admin_router.router)

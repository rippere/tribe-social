-- PrePost invite-only research trial (D1 database `prepost-trial`).
-- Apply: npx wrangler@4 d1 migrations apply prepost-trial --remote   (from apps/web)
--
-- Job lifecycle:
--   uploading → queued → submitted → running → complete
--                 ↑______________________|  (retry, at most 2, on infrastructure failure)
--   any non-terminal → failed (retries exhausted, bad input, or 72 h without a result)
--   any → deleted (the uploader deleted it, or the 30-day retention ran out)
-- A deleted/failed row keeps its invite reference so it still counts as a use.

CREATE TABLE jobs (
  id             TEXT PRIMARY KEY,               -- 16 random bytes, base64url; R2 key stem
  token_hash     TEXT NOT NULL UNIQUE,           -- sha256(result token); the token itself is never stored long-term
  token          TEXT,                           -- plaintext only until the result/failure email is sent, then NULL
  invite_hash    TEXT NOT NULL,                  -- sha256(invite code)
  email          TEXT NOT NULL,
  site           TEXT NOT NULL,                  -- origin the upload came from; links + signed URLs use it
  ext            TEXT NOT NULL CHECK (ext IN ('mp4', 'mov')),
  size_bytes     INTEGER NOT NULL,
  duration_s     REAL,
  status         TEXT NOT NULL CHECK (status IN ('uploading', 'queued', 'submitted', 'running', 'complete', 'failed', 'deleted')),
  attempts       INTEGER NOT NULL DEFAULT 0,     -- RunPod submissions so far
  runpod_job_id  TEXT,
  lease_until    INTEGER,                        -- epoch ms; past it, a submitted/running job is presumed lost
  created_at     INTEGER NOT NULL,               -- epoch ms
  submitted_at   INTEGER,
  started_at     INTEGER,
  completed_at   INTEGER,
  delay_ms       INTEGER,                        -- RunPod delayTime (queue + cold start)
  execution_ms   INTEGER,                        -- RunPod executionTime
  cold_start     INTEGER,                        -- 1 when the job was the worker's first
  error          TEXT,
  result_json    TEXT,                           -- the result page's data (no video, no frames)
  has_activity   INTEGER NOT NULL DEFAULT 0,     -- results/<id>/activity.bin exists in R2
  expires_at     INTEGER,                        -- epoch ms; result deleted after this (30 days)
  notified_at    INTEGER
);

CREATE INDEX jobs_status_created ON jobs (status, created_at);
CREATE INDEX jobs_invite ON jobs (invite_hash, status);
CREATE INDEX jobs_runpod ON jobs (runpod_job_id);

-- Dispatcher bookkeeping: tick lock and the last workersMax we set on RunPod.
CREATE TABLE trial_state (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);

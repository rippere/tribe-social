-- Terminal side effects are retried by the dispatcher's sweeper until settled:
--   cleaned         1 once the upload (and, for failed/deleted jobs, the activity) is gone from R2
--   email_attempts  result/failure email tries; the plaintext token is dropped at 5 even if unsent
ALTER TABLE jobs ADD COLUMN cleaned INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN email_attempts INTEGER NOT NULL DEFAULT 0;
CREATE INDEX jobs_unsettled ON jobs (status, cleaned);

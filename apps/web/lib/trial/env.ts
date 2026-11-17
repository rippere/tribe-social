// Bindings and secrets shared by the trial's Pages Functions (functions/api/trial/*)
// and the dispatcher Worker (apps/trial-dispatcher). Minimal structural types so the
// code needs no @cloudflare/workers-types dependency.

export interface D1Result<T = Record<string, unknown>> {
  results: T[]
  meta: { changes: number; last_row_id?: number }
}

export interface D1PreparedStatement {
  bind(...values: unknown[]): D1PreparedStatement
  first<T = Record<string, unknown>>(): Promise<T | null>
  all<T = Record<string, unknown>>(): Promise<D1Result<T>>
  run(): Promise<D1Result>
}

export interface D1Database {
  prepare(sql: string): D1PreparedStatement
  batch(statements: D1PreparedStatement[]): Promise<D1Result[]>
}

export interface R2Object {
  key: string
  size: number
  body: ReadableStream
  httpMetadata?: { contentType?: string }
  arrayBuffer(): Promise<ArrayBuffer>
}

export interface R2Bucket {
  get(key: string): Promise<R2Object | null>
  head(key: string): Promise<{ key: string; size: number } | null>
  put(
    key: string,
    value: ArrayBuffer | ArrayBufferView | ReadableStream | string,
    options?: { httpMetadata?: { contentType?: string } },
  ): Promise<unknown>
  delete(keys: string | string[]): Promise<void>
  list(options?: { prefix?: string; limit?: number }): Promise<{ objects: { key: string }[] }>
}

export interface KVNamespace {
  get(key: string): Promise<string | null>
  put(key: string, value: string, options?: { expirationTtl?: number; expiration?: number }): Promise<void>
  delete(key: string): Promise<void>
}

export type WaitUntil = (p: Promise<unknown>) => void

export interface TrialEnv {
  /** D1 `prepost-trial`: jobs + dispatcher state (migrations/). */
  TRIAL_DB: D1Database
  /** R2 `prepost-trial`: uploads/<id>.<ext> (lifecycle: 3 days) and results/<id>/. */
  TRIAL_BUCKET: R2Bucket
  /** HMAC key for signed blob URLs and the RunPod webhook. Secret. */
  TRIAL_SIGNING_KEY?: string
  RESEND_API_KEY?: string
  WAITLIST_FROM?: string
}

export interface PagesEnv extends TrialEnv {
  /** Waitlist + invites: signup:<email>, invite:<code>. */
  WAITLIST: KVNamespace
}

export interface DispatcherEnv extends TrialEnv {
  RUNPOD_API_KEY?: string
  RUNPOD_ENDPOINT_ID: string
  RUNPOD_ENDPOINT_NAME: string
  RUNPOD_TEMPLATE_ID: string
  RUNPOD_NETWORK_VOLUME_ID?: string
  /** Always AMPERE_80 (A100 80 GB). TRIBE v2 does not fit smaller cards. */
  RUNPOD_GPU_IDS: string
  RUNPOD_IDLE_TIMEOUT_S?: string
}

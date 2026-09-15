# apps/web — TRIBE dashboard (Next.js)

Next.js 16 (App Router) / React 19 client for the TRIBE scorer. **Pure client of `apps/api`** — no route handlers of its own.

## Pages
- `/` — landing (`app/page.tsx`)
- `/dashboard` — corpus analytics (7× `components/corpus/*`, recharts)
- `/scorer` — score-a-clip, 3 steps: `VideoDropzone` → `JobProgress` → `ResultsCard` (`ScoreGauge` · `ROIRadar` · `TemporalTimeline` · `RevisionPanel`)

## Data
All fetch goes through `lib/api.ts` (SWR): `GET /corpus`, `/corpus/stats`, `/health`; `POST /jobs` (upload mp4 ≤50MB, or a YouTube/IG URL) → poll `GET /jobs/{id}`. API base ← env `NEXT_PUBLIC_API_URL` (`localhost:8000` in dev).

## Run
`npm run dev` (also `build`, `start`). Framework gotchas: [`AGENTS.md`](AGENTS.md).
Full component + data-flow map: [`../../docs/CODEMAPS/frontend.md`](../../docs/CODEMAPS/frontend.md).

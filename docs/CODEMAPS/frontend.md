# Frontend — tribe-social/apps/web
<!-- Generated: 2026-09-17 | Scope: Next.js 16 App Router / React 19 | Token estimate: ~800 -->

Pure client of `apps/api` — **no route handlers, no app/api**. Stack: next 16.2.6, react 19.2.4, swr 2, recharts 3, react-dropzone 15, tailwind 4, shadcn.

## Page tree (app/)
```
/           app/page.tsx            landing — HeroSection · AudienceSection · BrainRegionSection (in-file, static)
/dashboard  app/dashboard/page.tsx  (client) corpus analytics
/scorer     app/scorer/page.tsx     (client) score-a-clip, 3-step useState machine
layout      app/layout.tsx → NavBar + children ; app/globals.css (tailwind v4)
```

## Scorer flow (`app/scorer/page.tsx`, jobId→result)
`VideoDropzone` (upload) → `JobProgress` (poll) → `ResultsCard` (result)
`ResultsCard` composes → `ScoreGauge` (composite) · `ROIRadar` (roi vs corpus_roi_means, recharts radar) · `TemporalTimeline` (per-second line) · `RevisionPanel` (weak-ROI tips + hook templates)

## Dashboard (`app/dashboard/page.tsx`, 7× `components/corpus/*`)
`CorpusOverview` · `ScoreDistribution` · `TopVideosTable` · `ROIBarChart` · `CorrelationScatter` · `CorrelationHeatmap` · `GoNoGoVerdict` (recharts)
`components/ui/*` = shadcn primitives · `components/layout/NavBar.tsx` (sticky, usePathname)

## Data flow (no global store; SWR server-state + useState UI-state)
API base: `lib/api.ts` `API_BASE` ← env `NEXT_PUBLIC_API_URL` (throws in prod if unset; `localhost:8000` dev). `lib/api.ts` is the **only** fetch layer.
```
Dashboard  useSWR('/corpus') + useSWR('/corpus/stats')      → GET /corpus, /corpus/stats
Scorer     fetchHealth()                                    → GET /health  (mock|pod|real badge)
Upload     VideoDropzone (react-dropzone: mp4 ≤50MB, 1 file) OR URL tab
             → submitJob(file?, url?)  multipart FormData    → POST /jobs → job_id
Poll       JobProgress useSWR('/jobs/{id}', refresh 2s)      → GET /jobs/{id}  (stops complete/failed, latches 404, 30-min ceiling)
```
`lib/types.ts` mirrors API models (JobResponse, ScoreResult, CorpusStats, InferenceMode). `lib/utils.ts` = `cn()`.

## Deploy
`railway.toml` (NIXPACKS, `npm run start`, healthcheck `/`). Env: `NEXT_PUBLIC_API_URL`. Framework rules: `apps/web/AGENTS.md` (`CLAUDE.md` just `@AGENTS.md`).

## Known issues
- **Stale landing-page hardcodes:** `app/page.tsx` hardcodes a "63.8" corpus average and 12/8/4 verdict chips rather than reading `/corpus/stats`. These drift from the real corpus every time it is rescored. Fix by fetching, not by editing the numbers.
- **Scoring stays server-side:** `lib/scoring.ts` must not re-implement composite weights, verdicts, or correlation. Those have one home (`packages/tribe_scoring/composite.py`) and reach the client through the API.

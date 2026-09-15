# Frontend — tribe-social/apps/web
<!-- Generated: 2026-09-15 | Scope: Next.js 16 App Router / React 19 | Token estimate: ~800 -->

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

## ⚠ Findings
- **Triple composite-weights home:** `lib/scoring.ts` re-implements weights / computeComposite / computeVerdict / pearsonR **client-side** — a THIRD copy, alongside `packages/tribe_scoring._BATCH_MASKS` (pod) and `apps/api/services/scoring.py COMPOSITE_WEIGHTS`. One rule, three homes → drift risk.
- **Stale hardcodes:** `app/page.tsx` hardcodes "63.8" corpus avg + 12/8/4 verdict chips (not API-driven) — drifts from the real corpus.
- **`apps/web/README.md`** was create-next-app boilerplate (replaced this sweep).

# CODEMAPS — system map (contract)

**What this is:** the monorepo's system map — token-lean cards answering *what is X*, *how X connects*, and *what else moves if I change X*. The root `CLAUDE.md` is the map entry; these cards are the shelves. Load one card, not the tree.

**Reads:** the live code under `apps/`, `packages/`, `research/`, `docs/`.
**Regenerate:** re-run the codemap sweep after major `apps/` or `research/` changes; bump the `<!-- Generated: … -->` header in each card.
**Human check:** a card is stale the moment code moves under it — treat a mismatch as a bug in the card, not the code.

## Cards
| Card | Answers |
|---|---|
| `architecture.md` | system boundaries + the scoring lifecycle |
| `backend.md` | api routes · services · pod/handler · tribe_scoring |
| `frontend.md` | apps/web pages · components · data flow |
| `data.md` | CSV schemas · the 7-ROI model · pipeline |
| `dependencies.md` | external services · Python/Node deps · deploy |

## Change-impact index — what else moves if I change X
Facts that live in MORE THAN ONE home. Change one, you must change all — the top two rows are **active drift today**, not hypotheticals (see `../../.reports/codemap-diff.txt`).

| If you change… | You must also touch | Card |
|---|---|---|
| **ROI composite weights / verdict thresholds** | `packages/tribe_scoring._WEIGHTS` (pod, 7-ROI) · `apps/api/app/services/scoring.py::COMPOSITE_WEIGHTS` (5-ROI) · `apps/web/lib/scoring.ts::COMPOSITE_WEIGHTS` (5-ROI). **Already divergent** — research validates a different composite than the product ships. | backend · frontend |
| **ROI set / names** | pod (functional names) · api `_map_runpod_output_to_roi` + `ROI_COLS` (anatomical) · web `lib/types.ts` + `lib/scoring.ts` · `research/scores.csv` columns | data · backend |
| **engagement schema** | `research/engagement.csv` · `engagement_template.csv` (drift: `saves` vs `platform`/`likes`) · `apps/api/scripts/build_corpus_json.py` · `research/phase1b_correlation.py` | data |
| **scoring backend selection** | env precedence in `apps/api/app/services/inference.py` (`POD_URL` → `RUNPOD_*` → mock) | backend |
| **VALIDATION protocol** | single home `docs/VALIDATION-PROTOCOL-AND-ROADMAP.md`; linked from `research/` + `docs/canon/` (pointer stub) | — |

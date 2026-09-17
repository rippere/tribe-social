# CODEMAPS — system map (contract)

**What this is:** the monorepo's system map — token-lean cards answering *what is X*, *how does X connect*, and *what else moves if I change X*. The root `CLAUDE.md` is the map entry; these cards are the shelves. Load one card, not the tree.

**Reads:** the live code under `apps/`, `packages/`, and `research/`.

**Regenerate:** re-run the codemap sweep after major `apps/` or `research/` changes, and bump the `<!-- Generated: … -->` header in each card you touch.

**Human check:** a card is stale the moment code moves under it — treat a mismatch as a bug in the card, not in the code. Update the card in the same PR as the change (see `CONTRIBUTING.md`).

## Cards
| Card | Answers |
|---|---|
| `architecture.md` | system boundaries + the scoring lifecycle |
| `backend.md` | api routes · services · pod/handler · tribe_scoring |
| `frontend.md` | apps/web pages · components · data flow |
| `data.md` | CSV schemas · the 7-ROI model · pipeline |
| `dependencies.md` | external services · Python/Node deps · deploy |

## Change-impact index — what else moves if I change X

Facts that live in MORE THAN ONE home. Change one, you must change all.

| If you change… | You must also touch | Card |
|---|---|---|
| **ROI composite weights / verdict thresholds** | ✅ **ONE home:** `packages/tribe_scoring/composite.py` (`ROI_WEIGHTS`, `POST_THRESHOLD`, `REVISE_THRESHOLD`, `compute_composite_raw`, `scale_to_100`, `compute_verdict`). Pod computes `composite_raw`; API scales to the corpus range and serves `verdict`; web renders the API's values. Do not re-implement in TS or in the API. | backend · frontend |
| **ROI set / names** | pod (functional names) · api `_map_runpod_output_to_roi` + `ROI_COLS` (anatomical) · web `lib/types.ts` · `research/scores.csv` columns | data · backend |
| **engagement schema** | `research/engagement.csv` · `research/engagement_template.csv` (known drift: `saves` vs `platform`/`likes`) · `apps/api/scripts/build_corpus_json.py` · `research/phase1b_correlation.py` | data |
| **scoring backend selection** | env precedence in `apps/api/app/services/inference.py` (`POD_URL` → `RUNPOD_*` → mock) | backend |
| **validation protocol** | single home: `docs/VALIDATION-PROTOCOL-AND-ROADMAP.md` | — |

## Open items
- **Engagement schema drift** (see `data.md`) — `engagement_template.csv` carries `saves`, the live `engagement.csv` does not. Reconcile before engagement is used as a study outcome.
- **Stale landing-page hardcodes** (see `frontend.md`) — `apps/web/app/page.tsx` hardcodes corpus figures instead of reading them from the API.

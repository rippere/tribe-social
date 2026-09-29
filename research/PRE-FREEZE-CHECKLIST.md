# Hook test — pre-freeze checklist

Everything that has to be true before the freeze record in [`PREREGISTRATION.md`](PREREGISTRATION.md) §12 is filled in and any ad money is spent. Work top to bottom. An item is done when the evidence in the right-hand column exists, not when someone says it's handled.

Section numbers refer to `PREREGISTRATION.md` v0.3 unless marked otherwise.

## 1. Governance (before anyone shoots)

| # | Item | Owner | Done when |
|---|---|---|---|
| 1.1 | Pre-registration v0.3 and the stimulus gate merged to `main` | Ben | PR #2 merged |
| 1.2 | IRB decision (judgment call, not a registered gate): request an exemption determination if the write-up is headed for arXiv/ICWSM, or record why none is needed | Ben | Determination letter or written rationale saved in the project folder (not the repo) |
| 1.3 | Optional: advisor or PI named and has read the pre-registration before freeze | Ben | Name and date recorded here |
| 1.4 | OSF project created for third-party timestamping | Ben | OSF URL recorded; §12 has a place for it |
| 1.5 | Each of the six shooters has signed [`CLIP-PERMISSION.md`](CLIP-PERMISSION.md) | Ben | Six signed copies stored outside the repo |

Note: roadmap §2.9 (IRB, consent, YouTube OAuth) was written for the older creator-corpus protocol and is not a registered gate for v0.3. The outcome here is platform-reported ad delivery on an account Ben controls (§4, §5), so no third-party analytics access is involved. Clip permission is required (§13, §15); IRB and advisor are judgment calls.

## 2. Ad account (before the shoot finishes)

Meta reviews new ad accounts and individual ads. Finding a problem after freeze means a deviation, so check these early.

| # | Item | Done when |
|---|---|---|
| 2.1 | Meta ad account and Instagram professional account set up and linked | One test ad set approved and paused |
| 2.2 | Budget approved: about $580, plan $700 with a $200 reserve (§13) | Funding source confirmed |
| 2.3 | Delivery settings rehearsed on the test ad set: reach objective, CBO off, US 18–65, Reels-only placement, frequency cap 1/day (§4) | Screenshot of the test ad set's settings |
| 2.4 | Ad-set capacity: can the account run 72 ad sets at once? If not, plan waves of complete bases (§4) | Wave plan written, or "single wave" confirmed |
| 2.5 | Audio: every clip uses original or licensed audio. Ads with unlicensed music get rejected or muted, which would break the within-base design | Rule sent to all shooters before they shoot |

## 3. Stimuli

| # | Item | Done when |
|---|---|---|
| 3.1 | Every shooter has the stimulus spec: 1080x1920, 30 fps, 15–25 s, −14 LUFS ±1, exact 90-frame hooks (§3) | Spec sent |
| 3.2 | Lucas has checked each shooter's first base before they shoot the other two (§13) | Six first bases signed off |
| 3.3 | No identifiable bystanders without their own release; no restricted ad categories (§15) | Lucas confirms per base |
| 3.4 | All 72 clips pass `make validate-stimuli`. A failing base is re-edited or dropped now, never after freeze (§3) | Manifest written; hash goes in §12 |

## 4. Before freeze

| # | Item | Done when |
|---|---|---|
| 4.1 | Human-guess round complete. Nobody ranks a base they shot; interviewees agree first (§7a) | CSV written; hash goes in §12 |
| 4.2 | All 72 clips scored on TRIBE v2 (§6) | Feature file written; hash goes in §12 |
| 4.3 | Analysis script final and run once end to end on synthetic outcomes | Script hash goes in §12 |
| 4.4 | Freeze: tag the commit, fill every §12 line, register on OSF | §12 has no blanks |

Only after 4.4: launch all ad sets together. Pull results once, at the end (§9).

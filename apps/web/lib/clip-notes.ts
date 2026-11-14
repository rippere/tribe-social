import type { RegionKey } from '@/components/brain/contract'
import { clock, REGION_KEYS, type ClipContext } from '@/lib/clips'

/**
 * Plain-English, timestamped review notes for a scored clip, computed from its real
 * per-second TRIBE v2 prediction (no hand-written numbers). Each note says where to
 * look and why, in reviewer language. They describe the predicted response only; they
 * are not a forecast of views or retention (see the pre-registration).
 */
export type ClipNote = { from: number; to: number; title: string; body: string }

const WINDOW = 3

const AREA: Record<RegionKey, string> = {
  attention: 'attention',
  social: 'social (reading people)',
  language: 'language',
  valuation: 'value',
  auditory: 'sound',
  motion: 'motion',
  narrative: 'story',
}

const shotName = (shot: string) => shot.split(':')[0].trim().toLowerCase()

function shotAt(ctx: ClipContext, s: number) {
  return ctx.timeline.find(t => s >= t.from && s < t.to) ?? ctx.timeline[ctx.timeline.length - 1]
}

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / Math.max(xs.length, 1)
const span = (from: number, to: number) => `${clock(from)}–${clock(to)}`

export function clipNotes(ctx: ClipContext): ClipNote[] {
  const series = ctx.whole_cortex.mean_per_second
  if (series.length < WINDOW) return []

  const windows = Array.from({ length: series.length - WINDOW + 1 }, (_, i) => ({
    from: i,
    mean: mean(series.slice(i, i + WINDOW)),
  }))
  const weakest = windows.reduce((a, b) => (b.mean < a.mean ? b : a))
  const strongest = windows.reduce((a, b) => (b.mean > a.mean ? b : a))
  const notes: ClipNote[] = []

  const weakShot = shotName(shotAt(ctx, weakest.from + 1).shot)
  notes.push({
    from: weakest.from,
    to: weakest.from + WINDOW,
    title: `Weakest stretch, ${span(weakest.from, weakest.from + WINDOW)}`,
    body:
      weakest.from < WINDOW
        ? `The predicted response is lowest in the opening, during the ${weakShot} shot. Look here first in review: the first three seconds are where a viewer decides whether to stay.`
        : `The predicted response is lowest during the ${weakShot} shot. If the draft needs a cut, start here.`,
  })

  notes.push({
    from: strongest.from,
    to: strongest.from + WINDOW,
    title: `Strongest stretch, ${span(strongest.from, strongest.from + WINDOW)}`,
    body: `The predicted response peaks around the ${shotName(shotAt(ctx, strongest.from + 1).shot)} shot. Protect this moment in the edit, or ask whether it could come earlier.`,
  })

  if (ctx.timeline.length > 1) {
    const shots = ctx.timeline.map(t => ({
      name: shotName(t.shot),
      from: t.from,
      to: t.to,
      mean: mean(series.slice(t.from, Math.min(t.to, series.length))),
    }))
    const best = shots.reduce((a, b) => (b.mean > a.mean ? b : a))
    const worst = shots.reduce((a, b) => (b.mean < a.mean ? b : a))
    if (best !== worst) {
      notes.push({
        from: worst.from,
        to: worst.to,
        title: `Shot by shot, the ${worst.name} trails`,
        body: `Averaged over each shot, the ${best.name} (${span(best.from, best.to)}) carries the highest predicted response and the ${worst.name} (${span(worst.from, worst.to)}) the lowest.`,
      })
    }
  }

  const lead = REGION_KEYS.reduce((a, b) => (ctx.regions[b].mean > ctx.regions[a].mean ? b : a))
  const leadPeak = ctx.regions[lead].peak_second
  notes.push({
    from: leadPeak,
    to: leadPeak + 1,
    title: `Doing the most work: ${AREA[lead]}`,
    body: `Of the seven brain areas, ${AREA[lead]} has the highest predicted response across the clip, peaking at ${clock(leadPeak)} in the ${shotName(shotAt(ctx, leadPeak).shot)} shot.`,
  })

  return notes
}

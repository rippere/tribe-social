// Three-free constants and types shared by the landing hero (main bundle) and
// CortexHeroScene (lazy chunk). Keep three.js imports out of this file.

/** Mutable rotation state shared between pointer handlers and the render loop. */
export interface HeroRig {
  yaw: number
  pitch: number
  vel: number // rad/s
  dragging: boolean
  spin: boolean // idle auto-rotation on/off
  invalidate?: () => void // redraw request for on-demand frame loops
}

/**
 * Idle spin, rad/s: one full turn every ~105 s. Negative so a visitor first sees
 * the start view (left three-quarter front) swing to the plain left lateral view
 * and on to the back, rather than toward the less readable frontal view.
 */
export const HERO_SPIN = -0.06

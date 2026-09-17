// Signature brand backdrop: a faint honeycomb hex mesh (Grok-window feel)
// plus soft, region-tinted floating "bubbles". Purely decorative — sits
// behind content, ignores pointer events, and respects reduced-motion
// (motion is gated by the `.tribe-float` utility in globals.css).

// Flat-top hexagon geometry. R = center→vertex; a tile of 3R × R√3 with a
// hex at each corner plus one in the middle tiles seamlessly as a honeycomb.
const R = 26
const TILE_H = R * Math.sqrt(3)
const TILE_W = 3 * R

function hex(cx: number, cy: number): string {
  const pts = [0, 60, 120, 180, 240, 300].map((deg) => {
    const rad = (Math.PI / 180) * deg
    return `${(cx + R * Math.cos(rad)).toFixed(2)},${(cy + R * Math.sin(rad)).toFixed(2)}`
  })
  return `M${pts.join('L')}Z`
}

const HEX_PATH = [
  hex(0, 0),
  hex(TILE_W, 0),
  hex(0, TILE_H),
  hex(TILE_W, TILE_H),
  hex(TILE_W / 2, TILE_H / 2),
].join('')

// Region-palette bubbles. Kept few and low-opacity so the mesh stays the
// hero and the composition reads calm/simple rather than busy.
const BUBBLES = [
  { color: 'var(--color-roi-vmPFC)', top: '8%', left: '12%', size: 320, delay: '0s' },
  { color: 'var(--color-roi-TPJ)', top: '52%', left: '4%', size: 260, delay: '-4s' },
  { color: 'var(--color-accent)', top: '18%', left: '68%', size: 380, delay: '-8s' },
  { color: 'var(--color-roi-IFJa)', top: '62%', left: '74%', size: 300, delay: '-2s' },
  { color: 'var(--color-roi-area45)', top: '80%', left: '40%', size: 240, delay: '-6s' },
]

export default function HexBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
      {/* honeycomb mesh, faded toward the edges */}
      <svg
        className="absolute inset-0 h-full w-full [mask-image:radial-gradient(ellipse_100%_90%_at_50%_35%,black_55%,transparent_100%)]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern id="tribe-hex" width={TILE_W} height={TILE_H} patternUnits="userSpaceOnUse">
            <path
              d={HEX_PATH}
              fill="none"
              strokeWidth="1"
              style={{ stroke: 'var(--color-accent)', strokeOpacity: 0.35 }}
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#tribe-hex)" />
      </svg>

      {/* soft floating region bubbles */}
      {BUBBLES.map((b, i) => (
        <div
          key={i}
          className="tribe-float absolute rounded-full blur-3xl"
          style={{
            top: b.top,
            left: b.left,
            width: b.size,
            height: b.size,
            background: b.color,
            opacity: 0.1,
            animationDelay: b.delay,
          }}
        />
      ))}
    </div>
  )
}

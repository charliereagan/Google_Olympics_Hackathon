// design-system.md §6 — film-grain noise texture (5% opacity, monochrome).
// We render it as an inline SVG <feTurbulence> so the asset is code, not a
// binary commit. Fixed-positioned, pointer-events-none, behind interactive
// content but above the page background.

export function GrainOverlay() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[1]"
      style={{ opacity: 0.05, mixBlendMode: 'overlay' }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="100%"
        height="100%"
        preserveAspectRatio="none"
      >
        <filter id="grain-noise">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves="2"
            stitchTiles="stitch"
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain-noise)" />
      </svg>
    </div>
  );
}

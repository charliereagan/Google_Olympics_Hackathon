// design-system.md §6 — barely-visible vignette darkening corners by 15%.
// Fixed-positioned, pointer-events-none, sits above the grain overlay so
// the corners darken consistently regardless of grain density.

export function Vignette() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[2]"
      style={{
        background:
          'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.15) 100%)',
      }}
    />
  );
}

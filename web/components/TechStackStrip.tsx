/**
 * <TechStackStrip /> — the "credit roll" register at the bottom of each
 * Production Deck page (/floor, /publish-gate, /wire).
 *
 * Single source of truth so the three pages stay byte-identical. Style
 * lifted verbatim from web/app/floor/page.tsx so cross-page consistency
 * survives any future tweak. Mobile wraps; never scrolls horizontally.
 *
 * Server-renderable (no client state). Keep it that way.
 */

const PRODUCTS: ReadonlyArray<string> = [
  'BUILT ON GOOGLE ADK',
  '5 GEMINI MODELS',
  'VERTEX AI',
  'CLOUD RUN',
  'BIGQUERY',
  'FIRESTORE',
  'CLOUD STORAGE',
  'NANO BANANA PRO',
  'GEMINI GOOGLE SEARCH GROUNDING',
];

export function TechStackStrip() {
  return (
    <div
      aria-label="Google products in use"
      className="mt-8 px-4 pb-8 sm:px-6 sm:pb-10 flex justify-center"
    >
      <p
        className="text-center font-mono uppercase text-parchment/80"
        style={{
          fontSize: '11px',
          letterSpacing: '0.22em',
          lineHeight: 1.7,
        }}
      >
        {PRODUCTS.map((product, idx) => (
          <span key={product}>
            {idx > 0 && (
              <span className="mx-2 text-gold-warm/70">&middot;</span>
            )}
            {product}
          </span>
        ))}
      </p>
    </div>
  );
}

export default TechStackStrip;

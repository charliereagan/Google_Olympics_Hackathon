/**
 * <FooterCredit /> — persistent attribution line above the bottom-fixed nav.
 *
 * Per VPS-DEC-049: a mono-caps credit strip listing the tech stack that
 * powers the room. Olympic-broadcast register (lower-third style); no
 * marketing language. Renders in <Layout /> so it appears on every page.
 *
 * Compliance (PROJECT_BRIEF §7): Google Cloud is the only third-party
 * vendor surface allowed. The names listed here are product names, not
 * logos — text-only attribution is in-scope per the hackathon brief.
 */

export function FooterCredit() {
  return (
    <div
      role="contentinfo"
      aria-label="Tech stack credits"
      // Sits ABOVE the bottom-fixed <BroadcastNav /> (which is fixed bottom
      // at z-30). We give the credit row natural document flow so it scrolls
      // with content; the page bottom-padding in <Layout /> reserves space
      // so the nav strip never covers it.
      className="w-full border-t border-navy-light/60 bg-navy-deep px-4 py-4 sm:px-6 lg:px-10"
    >
      <p
        className="text-center font-mono text-[10px] uppercase text-parchment/70 sm:text-mono-sm"
        style={{ letterSpacing: '0.22em' }}
      >
        Built with Gemini 3.1 &middot; Cloud Run &middot; BigQuery &middot;
        Nano Banana Pro &middot; Vertex AI
      </p>
    </div>
  );
}

export default FooterCredit;

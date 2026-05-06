/**
 * <VerifiedClaims> — audit-trail ribbon stack. Hairlines only, no card
 * backgrounds. Mono slug | body-md cream claim | mono source citation.
 * Mobile collapses the source onto a second line. Spec: design-system.md
 * §6 + §8 (Evidence Drawer register), BUILD_SPEC §5.7, PROJECT_BRIEF §6.
 */

import type { StoryClaim } from '@/lib/story-fixture';

interface VerifiedClaimsProps {
  claims: StoryClaim[];
  total_checked: number;
  total_passed: number;
  total_removed: number;
}

export function VerifiedClaims({
  claims,
  total_checked,
  total_passed,
  total_removed,
}: VerifiedClaimsProps) {
  return (
    <section
      aria-label="Verified claims audit trail"
      className="mt-16 sm:mt-20"
    >
      {/* ---- Header — tracked-small-cap mono, slate-room ---- */}
      <h2 className="font-body text-caption uppercase tracking-[0.18em] text-slate-room">
        verified claims · {total_checked} checked · {total_passed} passed ·{' '}
        {total_removed} removed
      </h2>

      {/* ---- Top hairline rule ---- */}
      <div
        aria-hidden="true"
        className="mt-4 h-px w-full bg-navy-light"
      />

      {/* ---- Claim list ---- */}
      <ul className="divide-y divide-navy-light">
        {claims.map((claim) => (
          <li
            key={claim.slug}
            className="grid grid-cols-1 gap-y-2 py-5 sm:grid-cols-12 sm:gap-x-6 sm:gap-y-1 sm:py-6"
          >
            {/* Slug — mono, gold-warm/60, breaks long-word cleanly */}
            <span className="font-mono text-mono-sm uppercase tracking-[0.04em] text-gold-warm/60 sm:col-span-3 break-words">
              {claim.slug}
            </span>

            {/* Claim body — body-md cream */}
            <p className="font-body text-body-md leading-[1.65] text-cream sm:col-span-6">
              {claim.text}
            </p>

            {/* Source — mono, wire-time, right-aligned on sm: upward;
                left-aligned on mobile so it doesn't read as a footer. */}
            <span className="font-mono text-mono-sm text-wire-time sm:col-span-3 sm:text-right">
              {claim.source}
            </span>
          </li>
        ))}
      </ul>

      {/* ---- Bottom hairline rule ---- */}
      <div
        aria-hidden="true"
        className="h-px w-full bg-navy-light"
      />
    </section>
  );
}

export default VerifiedClaims;

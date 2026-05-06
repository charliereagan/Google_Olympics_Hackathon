import { ReactNode } from 'react';
import { DaysToLA28 } from './DaysToLA28';
import { GrainOverlay } from './GrainOverlay';
import { Vignette } from './Vignette';

// design-system.md — page chrome.
// Minimal: top gold-warm hairline, top-right LA28 counter, atmospheric
// overlays. NO hamburger menu. NO logo. NO marketing copy. CONSTITUTION
// §4 Rule 6 five-second test: a judge unfamiliar with the project should
// recognize the Wire as a working newsroom feed within 5 seconds — chrome
// must not stand in the way.

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="relative min-h-screen">
      {/* Top hairline — 1px gold-warm across the viewport. design-system.md §6. */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-x-0 top-0 z-20 h-px bg-gold-warm/60"
      />

      {/* Top-right LA28 counter. */}
      <header className="fixed right-6 top-4 z-20 flex items-center">
        <DaysToLA28 />
      </header>

      {/* Main content sits above grain + vignette. */}
      <main className="relative z-10">{children}</main>

      {/* Atmospheric overlays — pointer-events-none, low opacity. */}
      <GrainOverlay />
      <Vignette />
    </div>
  );
}

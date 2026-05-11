import { Layout } from '@/components/Layout';
import { MapView } from '@/components/MapView';

// /map — the stylized US map discovery surface (VPS-DEC-042).
//
// One of three discovery surfaces: The Map (geographic familiarity — "find
// your region"), The Field (abstract pattern discovery), The Stories
// (chronological/editorial). All funnel to the Broadcast.
//
// PROJECT_BRIEF §7 auto-DQ: no third-party tile providers. The map uses
// d3-geo + us-atlas TopoJSON (public-domain Census Bureau data) rendered to
// Canvas — NOT Mapbox, NOT Google Maps, NOT Leaflet. No third-party logo
// attribution is required.
//
// Server component shell. The interactive canvas + projection lives in
// <MapView />, which is a client component.

export default function MapPage() {
  return (
    <Layout>
      <section
        aria-label="The Map — places producing Team USA, plotted on a stylized map of the United States"
        className="relative flex h-screen w-full flex-col"
      >
        <header className="pointer-events-none absolute left-4 top-12 z-20 sm:left-6 sm:top-14">
          <p className="font-mono text-caption uppercase tracking-[0.18em] text-gold-warm">
            the map · places producing team usa
          </p>
          <p className="mt-1 font-italic italic text-italic-sm text-wire-text sm:text-italic-md">
            Find your region.
          </p>
        </header>
        {/* Canvas fills the rest of the viewport. Top padding makes room for
            the kicker; bottom padding leaves space for any future bottom nav
            so dots near the southern coast aren't covered. */}
        <div className="relative flex-1 px-2 pb-20 pt-24 sm:px-4 sm:pb-16 sm:pt-28 md:px-6">
          <MapView />
        </div>
      </section>
    </Layout>
  );
}

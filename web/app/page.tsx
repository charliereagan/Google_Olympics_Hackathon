import { Layout } from '@/components/Layout';
import WireFeed from '@/components/WireFeed';

// The root view IS the Wire. CONSTITUTION §4 Rule 6 — five-second test —
// bans a "Welcome to The Storyteller's Room" hero. The room boots into the
// Wire directly.
//
// Day-9: this surface now subscribes to the live SSE bridge at
// `/api/wire/stream` via `<WireFeed />` and renders each event with the
// canonical `<WireRow />`. NIL Redaction runs server-side before any event
// is written to Firestore (HOE-DEC-018). The frontend just renders what
// arrives — never the Firestore SDK directly (HOE-DEC-024).
//
// Container: max-w-3xl with the Pass-2 mobile-sweep rhythm
// (px-4 py-12 sm:px-6 sm:py-16 md:py-20). DaysToLA28 lives in <Layout />.

export default function HomePage() {
  return (
    <Layout>
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 md:py-20">
        <WireFeed />
      </section>
    </Layout>
  );
}

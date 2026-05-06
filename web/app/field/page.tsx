import { Layout } from '@/components/Layout';
import { Field } from '@/components/Field';

// /field — the editorial-celestial constellation surface (formerly /floor;
// VPS-DEC-038 freed the /floor route for the BUILD_SPEC §9 agent graph).
//
// Server component shell. The interactive Canvas + d3-force simulation
// lives in <Field />, which is a client component. Per CLAUDE.md decision
// filter, this surface serves demo moment #1 ("the room is alive") and
// hosts the demo's anchor for moment #3 ("the Equity Editor caused the
// anchor story") via the scripted intervention pulse.

export default function FieldPage() {
  return (
    <Layout>
      <section
        aria-label="The Field — constellation map of places that have produced Olympians and Paralympians"
        className="relative h-screen w-full"
      >
        <header className="pointer-events-none absolute left-6 top-4 z-20">
          <p className="font-body text-caption uppercase tracking-[0.18em] text-slate-room">
            the field
          </p>
          <p className="mt-1 font-italic italic text-italic-sm text-wire-text">
            places, programs, patterns
          </p>
        </header>
        <Field />
      </section>
    </Layout>
  );
}

import { Layout } from '@/components/Layout';

// /story/[id] loading — kicker + two hairline rules. No spinner
// (CONSTITUTION §11 ban). Reduced-motion handled globally in globals.css.

export default function StoryLoading() {
  return (
    <Layout>
      <section className="mx-auto max-w-3xl px-4 py-24 sm:px-6 sm:py-32">
        <p className="font-mono text-mono-sm uppercase tracking-[0.18em] text-slate-room">loading story</p>
        <div aria-hidden="true" className="mt-6 h-px w-1/2 bg-gold-warm/40" />
        <div aria-hidden="true" className="mt-3 h-px w-1/3 bg-gold-warm/30" />
      </section>
    </Layout>
  );
}

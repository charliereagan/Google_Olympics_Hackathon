import { Layout } from '@/components/Layout';
import InvestigationStream from '@/components/InvestigationStream';

// /investigation/[id] — destination of the seed-prompt CTA (VPS-DEC-045).
// Fan submits prompt on `/` → routes here → watches the room work on their
// prompt at compressed time (4× per HOE-DEC-021/029) → "READ YOUR STORY"
// CTA on chain completion → /story/<id>.
//
// Server-component shell. InvestigationStream owns the SSE subscription,
// the investigation_id filter, completion detection, and the CTA card.

type Params = Promise<{ id: string }>;

export default async function InvestigationPage({
  params,
}: {
  params: Params;
}) {
  const { id } = await params;
  return (
    <Layout>
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 md:py-20">
        <InvestigationStream investigationId={id} />
      </section>
    </Layout>
  );
}

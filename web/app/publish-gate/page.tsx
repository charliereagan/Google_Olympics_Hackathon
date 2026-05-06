import { Layout } from '@/components/Layout';
import { PublishGatePanel } from '@/components/PublishGatePanel';

// /publish-gate — the trust panel (demo moment #5). Server-component shell;
// the audit feed renders inside the client `<PublishGatePanel />`.

export default function PublishGatePage() {
  return (
    <Layout>
      <PublishGatePanel />
    </Layout>
  );
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone build target — produces a self-contained .next/standalone/
  // tree the Cloud Run runner-stage Dockerfile copies. Reduces image size
  // by ~10x (no node_modules in final image; only what's traced).
  output: 'standalone',
  experimental: {
    // Per design-system.md and BUILD_SPEC §3.9
    serverActions: { bodySizeLimit: '2mb' },
  },
  // The Firestore Admin SDK uses gRPC (native bindings) and must not be
  // bundled by Next's webpack/turbopack pass — keep it as a real Node
  // require at runtime. The SSE Route Handler at app/api/wire/stream/route.ts
  // depends on this. (HOE-DEC-024.)
  serverExternalPackages: ['@google-cloud/firestore'],
};

module.exports = nextConfig;

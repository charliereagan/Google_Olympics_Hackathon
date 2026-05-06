// Server-side Firestore Admin client.
//
// Per HOE-DEC-024: the Next.js Route Handler holds a server-side `onSnapshot`
// listener on `wire_events` and forwards events to clients over SSE — the
// frontend never talks to Firestore directly. This file is the single
// initialization point for that server-side client.
//
// Lazy-initialized so we don't hit the SDK at build time (Next.js statically
// imports route modules during `next build`; constructing a Firestore client
// at module top-level would fire credential lookups in CI).
//
// Auth: Application Default Credentials. Local dev uses
// `gcloud auth application-default login`; Cloud Run uses the attached
// service account.

import { Firestore } from '@google-cloud/firestore';

let _db: Firestore | null = null;

export function getFirestore(): Firestore {
  if (_db) return _db;
  _db = new Firestore({
    projectId:
      process.env.GOOGLE_CLOUD_PROJECT ?? 'predictive-fx-495200-j4',
  });
  return _db;
}

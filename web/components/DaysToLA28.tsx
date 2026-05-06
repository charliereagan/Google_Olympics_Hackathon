'use client';

import { useEffect, useState } from 'react';
import { LA28_OPENING } from '@/lib/constants';

// design-system.md §11 (one-line decision 5): days-to-LA28 counter, top-right.
// Computes client-side to avoid SSR/CSR hydration drift across midnight UTC.
// Updates every minute (sufficient resolution for a day counter).

const MS_PER_DAY = 1000 * 60 * 60 * 24;

// UTC-midnight day diff: snap both endpoints to UTC-00:00 of their date, then
// take the integer day delta. Avoids the floor-of-fraction off-by-one that hit
// us at any wall-clock time past UTC midnight (review.md Q5).
function daysUntilUtcMidnight(target: Date, now: Date): number {
  const targetMidnightUtc = Date.UTC(
    target.getUTCFullYear(),
    target.getUTCMonth(),
    target.getUTCDate(),
  );
  const nowMidnightUtc = Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate(),
  );
  return Math.round((targetMidnightUtc - nowMidnightUtc) / MS_PER_DAY);
}

export function DaysToLA28() {
  const [days, setDays] = useState<number | null>(null);

  useEffect(() => {
    const update = () => {
      const diff = daysUntilUtcMidnight(LA28_OPENING, new Date());
      setDays(Math.max(0, diff));
    };
    update();
    const id = setInterval(update, 60_000);
    return () => clearInterval(id);
  }, []);

  if (days === null) return null;

  return (
    <span className="font-mono text-mono-sm text-gold-warm tabular-nums">
      {days.toLocaleString()} days to LA28
    </span>
  );
}

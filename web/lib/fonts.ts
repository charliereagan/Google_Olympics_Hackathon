import { Playfair_Display, Lora, Inter, JetBrains_Mono } from 'next/font/google';

// design-system.md §3 — locked typography. Loaded via next/font/google with
// display: 'block' (FOIT, never FOUT — better to wait for the typeface than
// show a fallback that breaks the editorial register).

export const fontDisplay = Playfair_Display({
  subsets: ['latin'],
  display: 'block',
  variable: '--font-display',
  weight: ['400', '500', '600', '700'],
  style: ['normal'],
});

export const fontItalic = Lora({
  subsets: ['latin'],
  display: 'block',
  variable: '--font-italic',
  weight: ['400', '500'],
  style: ['italic'], // Lora italic only — agent names + dek
});

export const fontBody = Inter({
  subsets: ['latin'],
  display: 'block',
  variable: '--font-body',
  weight: ['400', '500', '600'],
});

export const fontMono = JetBrains_Mono({
  subsets: ['latin'],
  display: 'block',
  variable: '--font-mono',
  weight: ['400', '500'],
});

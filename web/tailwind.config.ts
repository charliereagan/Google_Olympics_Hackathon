import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Locked tokens — design-system.md §2
        'navy-deep': '#0A1428',
        'navy-mid': '#1A2740',
        'navy-light': '#2C3E5A',
        'gold-warm': '#D4A84A',
        'gold-deep': '#A8842F',
        cream: '#F5EFE0',
        parchment: '#E8DDC4',
        'agitos-red': '#C8102E',
        'slate-room': '#5A6878', // namespaced to avoid Tailwind's `slate-*`
        'wire-text': '#B8C4D6',
        'wire-time': '#7A8AA0',
      },
      fontFamily: {
        display: ['var(--font-display)', 'Times New Roman', 'serif'],
        italic: ['var(--font-italic)', 'Times New Roman', 'serif'],
        body: ['var(--font-body)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'Menlo', 'monospace'],
      },
      fontSize: {
        // From design-system.md §3 type scale
        'display-xl': ['96px', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
        'display-lg': ['64px', { lineHeight: '1.1', letterSpacing: '-0.015em' }],
        'display-md': ['40px', { lineHeight: '1.15', letterSpacing: '-0.01em' }],
        'italic-md': ['22px', { lineHeight: '1.4' }],
        'italic-sm': ['15px', { lineHeight: '1.4' }],
        'body-md': ['17px', { lineHeight: '1.7' }],
        'body-sm': ['13px', { lineHeight: '1.5' }],
        caption: ['11px', { lineHeight: '1.3', letterSpacing: '0.12em' }],
        'mono-sm': ['12px', { lineHeight: '1.4', letterSpacing: '0.02em' }],
      },
      transitionTimingFunction: {
        // The custom curve from design-system.md §5
        room: 'cubic-bezier(0.32, 0.72, 0, 1)',
      },
    },
  },
  plugins: [],
};

export default config;

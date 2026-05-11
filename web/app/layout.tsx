import type { Metadata } from 'next';
import { fontDisplay, fontItalic, fontBody, fontMono } from '@/lib/fonts';
import './globals.css';

export const metadata: Metadata = {
  title: "The Storyteller's Room",
  description:
    'An AI broadcast room finding the hometown stories behind Team USA — places, programs, and patterns.',
  openGraph: {
    title: "The Storyteller's Room",
    description:
      'An AI broadcast room finding the hometown stories behind Team USA — places, programs, and patterns.',
    siteName: "The Storyteller's Room",
    type: 'website',
    locale: 'en_US',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${fontDisplay.variable} ${fontItalic.variable} ${fontBody.variable} ${fontMono.variable}`}
    >
      <body className="bg-navy-deep text-cream font-body antialiased">
        {children}
      </body>
    </html>
  );
}

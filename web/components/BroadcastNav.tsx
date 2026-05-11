'use client';

/**
 * <BroadcastNav /> — bottom-fixed broadcast-chrome nav strip on every page.
 *
 * Per VPS-DEC-041: tracked-small-caps mono links to the room's six surfaces.
 * Grouped into Front-of-House and Production Deck, separated by a hairline
 * divider — the absence of a kicker on FOH pages, and the divider here, do
 * the editorial work of saying "this side of the line is what the public
 * sees; that side is the room itself."
 *
 *   THE MAP · THE FIELD · THE STORIES  |  THE WIRE · THE FLOOR · THE GATE
 *
 * Visual:
 *   - position: fixed; bottom: 0; full width.
 *   - navy-deep background with 1px gold-warm/60 top hairline.
 *   - mono-sm, uppercase, letter-spacing 0.18em.
 *   - active route in gold-warm; inactive in cream; hover gold-deep.
 *   - mobile: horizontal scroll to keep all six visible without wrapping;
 *     the divider scrolls inline with the groups.
 *
 * No hamburger menu (forbidden — design-system.md §7). No icons. The room
 * has six views, and the strip lists them.
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface NavItem {
  href: string;
  label: string;
}

const FRONT_OF_HOUSE: NavItem[] = [
  { href: '/map', label: 'The Map' },
  { href: '/field', label: 'The Field' },
  { href: '/story', label: 'The Stories' },
];

const PRODUCTION_DECK: NavItem[] = [
  { href: '/wire', label: 'The Wire' },
  { href: '/floor', label: 'The Floor' },
  { href: '/publish-gate', label: 'The Gate' },
];

function isActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  if (href === '/') return pathname === '/';
  return pathname === href || pathname.startsWith(href + '/');
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string | null }) {
  const active = isActive(pathname, item.href);
  return (
    <li className="shrink-0">
      <Link
        href={item.href}
        className={[
          'font-mono text-mono-sm uppercase whitespace-nowrap transition-colors duration-200 ease-room',
          active ? 'text-gold-warm' : 'text-cream hover:text-gold-deep',
        ].join(' ')}
        style={{ letterSpacing: '0.18em' }}
        aria-current={active ? 'page' : undefined}
      >
        {item.label}
      </Link>
    </li>
  );
}

export function BroadcastNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-gold-warm/60 bg-navy-deep/95 backdrop-blur-[2px]"
    >
      <ul
        className="mx-auto flex max-w-6xl items-center justify-start gap-6 overflow-x-auto px-4 py-3 sm:justify-center sm:gap-10 sm:px-6 lg:px-10"
        style={{ scrollbarWidth: 'none' }}
      >
        {FRONT_OF_HOUSE.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} />
        ))}
        <li
          aria-hidden="true"
          className="mx-3 h-[18px] w-px shrink-0 bg-gold-warm/40 lg:mx-6"
        />
        {PRODUCTION_DECK.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} />
        ))}
      </ul>
    </nav>
  );
}

export default BroadcastNav;

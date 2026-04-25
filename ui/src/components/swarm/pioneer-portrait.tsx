"use client";

/**
 * Pioneer portrait silhouettes â€” one per Lamport worker role.
 *
 * Each SVG uses `currentColor` for the silhouette, and
 * `fill="var(--chat-bg,#0d0f1a)"` for cutout features (glass lenses, gaps)
 * so details are clearly visible at any role color.
 *
 * Role â†’ Pioneer mapping:
 *   researcher â†’ Claude Shannon    (side-part, bow-tie, round glasses)
 *   architect  â†’ Charles Babbage   (Victorian mutton chops, high collar, top hat brim)
 *   coder      â†’ Donald Knuth      (iconic round glasses, full beard, balding crown)
 *   devops     â†’ Vint Cerf         (full bushy beard, three-piece suit, prominent tie)
 *   analyst    â†’ Edgar Codd        (rectangular glasses, 1970s side-part, turtleneck)
 *   verifier   â†’ Tony Hoare        (rectangular glasses, silver hair, distinguished collar)
 */

export function PioneerPortrait({ role }: { role: string }) {
  const P = PORTRAITS[role.toLowerCase()] ?? PORTRAITS._default;
  return P;
}

const PORTRAITS: Record<string, React.ReactElement> = {
  /** Claude Shannon â€” clean side-parted hair, young 1940s academic */
  researcher: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* Hair â€” neat, side-parted left-to-right sweep */}
      <path
        d="M28 33C28 15 36 9 48 8C60 9 68 15 68 33
           C62 16 53 12 44 16C37 19 30 25 28 33Z"
        fill="currentColor"
      />
    </svg>
  ),

  /** Charles Babbage â€” Victorian mutton-chop sideburns, stiff high collar */
  architect: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Wide formal shoulders */}
      <path d="M13 96C13 78 30 69 48 67C66 69 83 78 83 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* High Victorian collar */}
      <path d="M37 66C35 61 35 54 41 52L48 51L55 52C61 54 61 61 59 66Z" fill="currentColor" fillOpacity=".9"/>
      {/* Neck */}
      <rect x="43" y="51" width="10" height="16" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="36" rx="20" ry="24" fill="currentColor"/>
      {/* Hair â€” slicked back formal */}
      <path
        d="M28 30C28 12 36 8 48 7C60 8 68 12 68 30
           C63 13 53 10 48 10C43 10 33 13 28 30Z"
        fill="currentColor"
      />
      {/* Mutton-chop sideburn â€” left */}
      <path d="M28 31C24 43 24 55 28 61C31 59 32 49 32 37Z" fill="currentColor" fillOpacity=".9"/>
      {/* Mutton-chop sideburn â€” right */}
      <path d="M68 31C72 43 72 55 68 61C65 59 64 49 64 37Z" fill="currentColor" fillOpacity=".9"/>
    </svg>
  ),

  /** Donald Knuth â€” round glasses, beard, and famously receding crown */
  coder: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* Balding crown â€” hair only at sides/back */}
      <path d="M28 32C28 18 32 11 38 9C32 12 28 19 28 32Z" fill="currentColor"/>
      <path d="M68 32C68 18 64 11 58 9C64 12 68 19 68 32Z" fill="currentColor"/>
      {/* Thin crown fringe */}
      <path d="M38 9C42 8 44 8 48 8C52 8 54 8 58 9" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" opacity=".45"/>
      {/* Beard â€” full, rounded */}
      <path
        d="M29 52C28 63 35 71 48 71C61 71 68 63 67 52
           C60 58 54 61 48 61C42 61 36 58 29 52Z"
        fill="currentColor" fillOpacity=".9"
      />
      {/* Moustache */}
      <path
        d="M35 49C40 52 44 51 48 50C52 51 56 52 61 49
           C57 47 52 47 48 47C44 47 39 47 35 49Z"
        fill="currentColor"
      />
      {/* Iconic round glasses â€” left */}
      <circle cx="38" cy="40" r="9" stroke="currentColor" strokeWidth="3"/>
      {/* Iconic round glasses â€” right */}
      <circle cx="58" cy="40" r="9" stroke="currentColor" strokeWidth="3"/>
      {/* Bridge */}
      <path d="M47 40H49" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
      {/* Temples */}
      <path d="M25 38L29 40" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M71 38L67 40" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  ),

  /** Vint Cerf â€” full bushy beard & moustache, suit with necktie */
  devops: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Wide shoulders */}
      <path d="M13 96C13 77 30 68 48 66C66 68 83 77 83 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Necktie */}
      <path d="M40 66L44 56L48 61L52 56L56 66Z" fill="currentColor" fillOpacity=".7"/>
      {/* Neck */}
      <rect x="43" y="56" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="37" rx="20" ry="24" fill="currentColor"/>
      {/* Hair */}
      <path
        d="M28 31C28 13 36 8 48 7C60 8 68 13 68 31
           C62 14 52 11 48 11C44 11 34 14 28 31Z"
        fill="currentColor"
      />
      {/* Full beard â€” extends well below chin */}
      <path
        d="M28 47C26 59 32 70 40 73C44 75 52 75 56 73
           C64 70 70 59 68 47C60 54 53 57 48 57C43 57 36 54 28 47Z"
        fill="currentColor" fillOpacity=".9"
      />
      {/* Thick moustache */}
      <path
        d="M31 45C37 50 42 50 48 49C54 50 59 50 65 45
           C59 42 53 42 48 42C43 42 37 42 31 45Z"
        fill="currentColor"
      />
    </svg>
  ),

  /** Edgar Codd â€” tidy 1970s side-parted hair, clean British academic */
  analyst: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* 1970s hair â€” slightly longer on sides, side-parted */}
      <path
        d="M28 33C28 14 37 9 48 8C59 9 68 14 68 33
           C62 16 51 12 42 16C34 20 29 26 28 33Z"
        fill="currentColor"
      />
      {/* Subtle side-part line */}
      <path d="M40 14C38 18 36 24 35 32" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fillOpacity="0" opacity=".35"/>
    </svg>
  ),

  /** Tony Hoare â€” rectangular academic glasses, distinguished silver look */
  verifier: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* Silver/receding hair â€” reduced opacity for grey effect */}
      <path
        d="M28 32C28 14 34 9 48 9C62 9 68 14 68 32
           C63 16 54 12 48 12C42 12 33 16 28 32Z"
        fill="currentColor" fillOpacity=".6"
      />
      {/* Rectangular academic glasses â€” left */}
      <rect x="29" y="33" width="15" height="10" rx="2" stroke="currentColor" strokeWidth="2.5"/>
      {/* Rectangular academic glasses â€” right */}
      <rect x="52" y="33" width="15" height="10" rx="2" stroke="currentColor" strokeWidth="2.5"/>
      {/* Bridge */}
      <path d="M44 38H52" stroke="currentColor" strokeWidth="2.5"/>
      {/* Temples */}
      <path d="M25 35L29 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <path d="M71 35L67 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),

  /** Fallback â€” generic professional silhouette */
  _default: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      <path d="M28 34C28 16 37 11 48 10C59 11 68 16 68 34Z" fill="currentColor"/>
    </svg>
  ),
};

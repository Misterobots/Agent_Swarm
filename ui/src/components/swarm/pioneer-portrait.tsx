"use client";

/**
 * Pioneer portrait silhouettes — one per Lamport worker role.
 *
 * Each SVG uses `currentColor` for the silhouette, and
 * `fill="var(--chat-bg,#0d0f1a)"` for cutout features (glass lenses, gaps)
 * so details are clearly visible at any role color.
 *
 * Role → Pioneer mapping:
 *   researcher → Claude Shannon    (side-part, bow-tie, round glasses)
 *   architect  → Charles Babbage   (Victorian mutton chops, high collar, top hat brim)
 *   coder      → Donald Knuth      (iconic round glasses, full beard, balding crown)
 *   devops     → Vint Cerf         (full bushy beard, three-piece suit, prominent tie)
 *   analyst    → Edgar Codd        (rectangular glasses, 1970s side-part, turtleneck)
 *   verifier   → Tony Hoare        (rectangular glasses, silver hair, distinguished collar)
 */

export function PioneerPortrait({ role }: { role: string }) {
  const P = PORTRAITS[role.toLowerCase()] ?? PORTRAITS._default;
  return P;
}

const PORTRAITS: Record<string, React.ReactElement> = {
  /** Claude Shannon — side-part, bow-tie, subtle round glasses */
  researcher: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders + suit */}
      <path d="M12 96C12 78 28 67 48 65C68 67 84 78 84 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Suit lapels — V-shape cutout */}
      <path d="M37 65L48 78L59 65L55 56L48 60L41 56Z" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".7"/>
      {/* Bow-tie */}
      <path d="M41 59L44 62L41 65L44 65L48 62L52 65L55 65L52 62L55 59L52 59L48 62L44 59Z" fill="currentColor" fillOpacity=".9"/>
      {/* Neck */}
      <rect x="43" y="55" width="10" height="12" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="36" rx="21" ry="25" fill="currentColor"/>
      {/* Ears */}
      <ellipse cx="27.5" cy="37" rx="4" ry="6" fill="currentColor"/>
      <ellipse cx="68.5" cy="37" rx="4" ry="6" fill="currentColor"/>
      <ellipse cx="27.5" cy="37" rx="2" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      <ellipse cx="68.5" cy="37" rx="2" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      {/* Hair — neat 1940s side part, sweeps left to right */}
      <path
        d="M27 30C27 12 36 7 48 7C60 7 69 12 69 30
           C64 13 54 10 46 13C38 17 30 23 27 30Z"
        fill="currentColor"
      />
      {/* Side-part line */}
      <path d="M43 11C41 15 39 21 38 29" stroke="var(--chat-bg,#0d0f1a)" strokeWidth="1.5" strokeLinecap="round" opacity=".5"/>
      {/* Eyebrows */}
      <path d="M34 26C37 24 41 24 44 25" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fillOpacity="0"/>
      <path d="M52 25C55 24 59 24 62 26" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fillOpacity="0"/>
      {/* Round glasses (Shannon wore glasses) — cutout lenses */}
      <circle cx="37" cy="33" r="8" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="2.5"/>
      <circle cx="59" cy="33" r="8" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="2.5"/>
      {/* Bridge + temples */}
      <path d="M45 33H51" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M23 31L29 33" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <path d="M73 31L67 33" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),

  /** Charles Babbage — Victorian, prominent mutton chops, top hat silhouette, monocle */
  architect: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Wide formal shoulders with coat */}
      <path d="M11 96C11 76 28 66 48 64C68 66 85 76 85 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* High Victorian collar / cravat */}
      <path d="M36 64L40 55L48 59L56 55L60 64Z" fill="currentColor" fillOpacity=".9"/>
      <path d="M40 55L44 60L48 57L52 60L56 55L52 52L48 55L44 52Z" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".5"/>
      {/* Neck */}
      <rect x="43" y="49" width="10" height="17" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="34" rx="20" ry="23" fill="currentColor"/>
      {/* Mutton-chop sideburn — left (very full, Victorian) */}
      <path d="M28 28C22 38 20 52 25 60C29 58 31 50 33 40L28 28Z" fill="currentColor" fillOpacity=".92"/>
      {/* Mutton-chop sideburn — right */}
      <path d="M68 28C74 38 76 52 71 60C67 58 65 50 63 40L68 28Z" fill="currentColor" fillOpacity=".92"/>
      {/* Inner ear detail visible between chops and head */}
      <path d="M27 34C24 42 24 50 27 56C30 54 31 48 31 40Z" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".2"/>
      <path d="M69 34C72 42 72 50 69 56C66 54 65 48 65 40Z" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".2"/>
      {/* Slicked-back formal hair */}
      <path
        d="M28 28C28 10 36 6 48 5C60 6 68 10 68 28
           C62 11 52 9 48 9C44 9 34 11 28 28Z"
        fill="currentColor"
      />
      {/* Monocle on right eye — Babbage detail */}
      <circle cx="57" cy="30" r="9" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="2.5"/>
      <path d="M66 36L70 42" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      {/* Eyebrow left */}
      <path d="M32 22C35 20 40 20 44 22" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fillOpacity="0"/>
    </svg>
  ),

  /** Donald Knuth — iconic round glasses, full beard, balding crown */
  coder: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M17 96C17 80 30 72 48 70C66 72 79 80 79 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="10" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="37" rx="21" ry="25" fill="currentColor"/>
      {/* Balding crown — hair only at sides */}
      <path d="M27 30C27 17 31 10 37 8C31 11 27 18 27 30Z" fill="currentColor"/>
      <path d="M69 30C69 17 65 10 59 8C65 11 69 18 69 30Z" fill="currentColor"/>
      {/* Thin crown fringe */}
      <path d="M37 8C41 7 44 7 48 7C52 7 55 7 59 8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" opacity=".4"/>
      {/* Ears — visible on the sides */}
      <ellipse cx="27.5" cy="36" rx="4.5" ry="6.5" fill="currentColor"/>
      <ellipse cx="68.5" cy="36" rx="4.5" ry="6.5" fill="currentColor"/>
      <ellipse cx="27.5" cy="36" rx="2.5" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      <ellipse cx="68.5" cy="36" rx="2.5" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      {/* Full beard — extends below chin */}
      <path
        d="M28 50C26 62 33 72 48 72C63 72 70 62 68 50
           C61 57 54 60 48 60C42 60 35 57 28 50Z"
        fill="currentColor" fillOpacity=".92"
      />
      {/* Moustache */}
      <path
        d="M34 47C39 51 43 50 48 49C53 50 57 51 62 47
           C57 44 52 44 48 44C44 44 39 44 34 47Z"
        fill="currentColor"
      />
      {/* Iconic LARGE round glasses — cutout lens areas */}
      <circle cx="37" cy="37" r="10" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="3.5"/>
      <circle cx="59" cy="37" r="10" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="3.5"/>
      {/* Bridge */}
      <path d="M47 37H49" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"/>
      {/* Temples */}
      <path d="M23 35L27 37" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
      <path d="M73 35L69 37" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
    </svg>
  ),

  /** Vint Cerf — very full beard, signature three-piece suit, prominent necktie */
  devops: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Wide three-piece suit shoulders */}
      <path d="M11 96C11 75 28 65 48 63C68 65 85 75 85 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Suit jacket lapels */}
      <path d="M36 63L42 52L48 57L54 52L60 63Z" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".5"/>
      {/* Prominent necktie — Cerf's signature */}
      <path d="M44 52L46 44L48 48L50 44L52 52L50 57L48 54L46 57Z" fill="currentColor" fillOpacity=".9"/>
      {/* Waistcoat visible between lapels */}
      <path d="M42 60L48 63L54 60L54 57L48 60L42 57Z" fill="currentColor" fillOpacity=".7"/>
      {/* Neck (hidden by beard) */}
      <rect x="43" y="51" width="10" height="14" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="34" rx="21" ry="25" fill="currentColor"/>
      {/* Ears */}
      <ellipse cx="27.5" cy="33" rx="4" ry="6" fill="currentColor"/>
      <ellipse cx="68.5" cy="33" rx="4" ry="6" fill="currentColor"/>
      <ellipse cx="27.5" cy="33" rx="2" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".35"/>
      <ellipse cx="68.5" cy="33" rx="2" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".35"/>
      {/* Hair */}
      <path
        d="M27 28C27 10 36 6 48 5C60 6 69 10 69 28
           C63 11 52 8 48 8C44 8 33 11 27 28Z"
        fill="currentColor"
      />
      {/* VERY full, voluminous beard — Cerf's defining trait */}
      <path
        d="M26 45C23 58 29 72 40 76C44 78 52 78 56 76
           C67 72 73 58 70 45C62 53 54 57 48 57C42 57 34 53 26 45Z"
        fill="currentColor" fillOpacity=".95"
      />
      {/* Thick moustache merging with beard */}
      <path
        d="M30 43C36 48 42 48 48 47C54 48 60 48 66 43
           C60 39 53 39 48 39C43 39 36 39 30 43Z"
        fill="currentColor"
      />
      {/* Eyebrows — prominent under hearing-aid-framed glasses */}
      <path d="M32 22C35 20 40 20 43 21" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fillOpacity="0"/>
      <path d="M53 21C56 20 61 20 64 22" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fillOpacity="0"/>
    </svg>
  ),

  /** Edgar Codd — rectangular glasses, 1970s side-part, turtleneck collar */
  analyst: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M17 96C17 80 30 72 48 70C66 72 79 80 79 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Turtleneck collar */}
      <path d="M37 72C35 67 34 60 38 57L48 55L58 57C62 60 61 67 59 72Z" fill="currentColor" fillOpacity=".9"/>
      <ellipse cx="48" cy="56" rx="10" ry="4" fill="currentColor" fillOpacity=".8"/>
      {/* Neck */}
      <rect x="43" y="53" width="10" height="19" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="37" rx="21" ry="25" fill="currentColor"/>
      {/* Ears */}
      <ellipse cx="27.5" cy="37" rx="4.5" ry="6" fill="currentColor"/>
      <ellipse cx="68.5" cy="37" rx="4.5" ry="6" fill="currentColor"/>
      <ellipse cx="27.5" cy="37" rx="2.5" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      <ellipse cx="68.5" cy="37" rx="2.5" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      {/* 1970s hair — slightly longer, side-parted */}
      <path
        d="M27 31C27 12 36 7 48 7C60 7 69 12 69 31
           C63 14 51 11 42 14C34 18 28 25 27 31Z"
        fill="currentColor"
      />
      {/* Side-part line */}
      <path d="M42 10C40 14 38 21 37 29" stroke="var(--chat-bg,#0d0f1a)" strokeWidth="1.5" strokeLinecap="round" opacity=".45"/>
      {/* Sideburns — 1970s style */}
      <path d="M27 35C25 42 25 50 27 55C29 53 30 47 30 40Z" fill="currentColor" fillOpacity=".8"/>
      <path d="M69 35C71 42 71 50 69 55C67 53 66 47 66 40Z" fill="currentColor" fillOpacity=".8"/>
      {/* Eyebrows */}
      <path d="M33 25C36 23 40 23 44 24" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fillOpacity="0"/>
      <path d="M52 24C56 23 60 23 63 25" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fillOpacity="0"/>
      {/* Rectangular 1970s glasses — cutout lenses */}
      <rect x="28" y="30" width="16" height="11" rx="2" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="2.5"/>
      <rect x="52" y="30" width="16" height="11" rx="2" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="2.5"/>
      {/* Bridge + temples */}
      <path d="M44 35H52" stroke="currentColor" strokeWidth="2.5"/>
      <path d="M23 32L28 33" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <path d="M73 32L68 33" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      {/* Slight moustache */}
      <path d="M40 46C43 48 45 47 48 47C51 47 53 48 56 46C53 44 51 44 48 44C45 44 43 44 40 46Z"
        fill="currentColor" fillOpacity=".7"/>
    </svg>
  ),

  /** Tony Hoare — large rectangular glasses, distinguished silver hair, bow-tie */
  verifier: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders + suit */}
      <path d="M14 96C14 78 29 68 48 66C67 68 82 78 82 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Suit lapels */}
      <path d="M36 66L42 55L48 60L54 55L60 66Z" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".5"/>
      {/* Academic bow-tie */}
      <path d="M42 58L45 62L42 65L45 65L48 62L51 65L54 65L51 62L54 58L51 58L48 62L45 58Z" fill="currentColor" fillOpacity=".9"/>
      {/* Neck */}
      <rect x="43" y="54" width="10" height="13" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="37" rx="21" ry="25" fill="currentColor"/>
      {/* Ears */}
      <ellipse cx="27.5" cy="37" rx="4.5" ry="6.5" fill="currentColor"/>
      <ellipse cx="68.5" cy="37" rx="4.5" ry="6.5" fill="currentColor"/>
      <ellipse cx="27.5" cy="37" rx="2.5" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      <ellipse cx="68.5" cy="37" rx="2.5" ry="3.5" fill="var(--chat-bg,#0d0f1a)" fillOpacity=".4"/>
      {/* Distinguished/silver hair — lower opacity for grey appearance, receding slightly */}
      <path
        d="M27 29C27 11 34 7 48 7C62 7 69 11 69 29
           C64 13 54 10 48 10C42 10 32 13 27 29Z"
        fill="currentColor" fillOpacity=".55"
      />
      {/* Temple hair — silver sides visible */}
      <path d="M27 29C25 36 25 44 27 50C30 48 31 42 31 35Z" fill="currentColor" fillOpacity=".55"/>
      <path d="M69 29C71 36 71 44 69 50C66 48 65 42 65 35Z" fill="currentColor" fillOpacity=".55"/>
      {/* Eyebrows — distinguished, slightly bushy */}
      <path d="M31 24C34 22 39 21 44 23" stroke="currentColor" strokeWidth="3" strokeLinecap="round" fillOpacity="0" opacity=".8"/>
      <path d="M52 23C57 21 62 22 65 24" stroke="currentColor" strokeWidth="3" strokeLinecap="round" fillOpacity="0" opacity=".8"/>
      {/* Large rectangular academic glasses — Hoare's defining feature */}
      <rect x="27" y="29" width="17" height="13" rx="2.5" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="3"/>
      <rect x="52" y="29" width="17" height="13" rx="2.5" fill="var(--chat-bg,#0d0f1a)" stroke="currentColor" strokeWidth="3"/>
      {/* Bridge + temples */}
      <path d="M44 35H52" stroke="currentColor" strokeWidth="3"/>
      <path d="M22 32L27 33" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M74 32L69 33" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  ),

  /** Fallback — generic professional silhouette */
  _default: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      <path d="M17 96C17 80 30 72 48 70C66 72 79 80 79 96Z" fill="currentColor" fillOpacity=".85"/>
      <rect x="43" y="60" width="10" height="12" fill="currentColor" fillOpacity=".9"/>
      <ellipse cx="48" cy="37" rx="20" ry="24" fill="currentColor"/>
      <ellipse cx="28" cy="37" rx="4" ry="5.5" fill="currentColor"/>
      <ellipse cx="68" cy="37" rx="4" ry="5.5" fill="currentColor"/>
      <path d="M28 31C28 13 36 8 48 8C60 8 68 13 68 31Z" fill="currentColor"/>
    </svg>
  ),
};


export function PioneerPortrait({ role }: { role: string }) {
  const P = PORTRAITS[role.toLowerCase()] ?? PORTRAITS._default;
  return P;
}

const PORTRAITS: Record<string, React.ReactElement> = {
  /** Claude Shannon — clean side-parted hair, young 1940s academic */
  researcher: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* Hair — neat, side-parted left-to-right sweep */}
      <path
        d="M28 33C28 15 36 9 48 8C60 9 68 15 68 33
           C62 16 53 12 44 16C37 19 30 25 28 33Z"
        fill="currentColor"
      />
    </svg>
  ),

  /** Charles Babbage — Victorian mutton-chop sideburns, stiff high collar */
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
      {/* Hair — slicked back formal */}
      <path
        d="M28 30C28 12 36 8 48 7C60 8 68 12 68 30
           C63 13 53 10 48 10C43 10 33 13 28 30Z"
        fill="currentColor"
      />
      {/* Mutton-chop sideburn — left */}
      <path d="M28 31C24 43 24 55 28 61C31 59 32 49 32 37Z" fill="currentColor" fillOpacity=".9"/>
      {/* Mutton-chop sideburn — right */}
      <path d="M68 31C72 43 72 55 68 61C65 59 64 49 64 37Z" fill="currentColor" fillOpacity=".9"/>
    </svg>
  ),

  /** Donald Knuth — round glasses, beard, and famously receding crown */
  coder: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* Balding crown — hair only at sides/back */}
      <path d="M28 32C28 18 32 11 38 9C32 12 28 19 28 32Z" fill="currentColor"/>
      <path d="M68 32C68 18 64 11 58 9C64 12 68 19 68 32Z" fill="currentColor"/>
      {/* Thin crown fringe */}
      <path d="M38 9C42 8 44 8 48 8C52 8 54 8 58 9" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" opacity=".45"/>
      {/* Beard — full, rounded */}
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
      {/* Iconic round glasses — left */}
      <circle cx="38" cy="40" r="9" stroke="currentColor" strokeWidth="3"/>
      {/* Iconic round glasses — right */}
      <circle cx="58" cy="40" r="9" stroke="currentColor" strokeWidth="3"/>
      {/* Bridge */}
      <path d="M47 40H49" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
      {/* Temples */}
      <path d="M25 38L29 40" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M71 38L67 40" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  ),

  /** Vint Cerf — full bushy beard & moustache, suit with necktie */
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
      {/* Full beard — extends well below chin */}
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

  /** Edgar Codd — tidy 1970s side-parted hair, clean British academic */
  analyst: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* 1970s hair — slightly longer on sides, side-parted */}
      <path
        d="M28 33C28 14 37 9 48 8C59 9 68 14 68 33
           C62 16 51 12 42 16C34 20 29 26 28 33Z"
        fill="currentColor"
      />
      {/* Subtle side-part line */}
      <path d="M40 14C38 18 36 24 35 32" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fillOpacity="0" opacity=".35"/>
    </svg>
  ),

  /** Tony Hoare — rectangular academic glasses, distinguished silver look */
  verifier: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      {/* Shoulders */}
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      {/* Neck */}
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      {/* Head */}
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      {/* Silver/receding hair — reduced opacity for grey effect */}
      <path
        d="M28 32C28 14 34 9 48 9C62 9 68 14 68 32
           C63 16 54 12 48 12C42 12 33 16 28 32Z"
        fill="currentColor" fillOpacity=".6"
      />
      {/* Rectangular academic glasses — left */}
      <rect x="29" y="33" width="15" height="10" rx="2" stroke="currentColor" strokeWidth="2.5"/>
      {/* Rectangular academic glasses — right */}
      <rect x="52" y="33" width="15" height="10" rx="2" stroke="currentColor" strokeWidth="2.5"/>
      {/* Bridge */}
      <path d="M44 38H52" stroke="currentColor" strokeWidth="2.5"/>
      {/* Temples */}
      <path d="M25 35L29 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <path d="M71 35L67 36" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  ),

  /** Fallback — generic professional silhouette */
  _default: (
    <svg viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      <path d="M18 96C18 82 31 74 48 72C65 74 78 82 78 96Z" fill="currentColor" fillOpacity=".85"/>
      <rect x="43" y="62" width="10" height="11" fill="currentColor" fillOpacity=".9"/>
      <ellipse cx="48" cy="39" rx="20" ry="24" fill="currentColor"/>
      <path d="M28 34C28 16 37 11 48 10C59 11 68 16 68 34Z" fill="currentColor"/>
    </svg>
  ),
};

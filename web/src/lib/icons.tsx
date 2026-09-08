type P = { className?: string };

const S = ({ children, className }: P & { children: any }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.8}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className || "h-5 w-5"}
  >
    {children}
  </svg>
);

export const Icon = {
  overview: (p: P) => (
    <S {...p}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </S>
  ),
  automation: (p: P) => (
    <S {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
    </S>
  ),
  topics: (p: P) => (
    <S {...p}>
      <path d="M9 18l6-12M6 8l-4 4 4 4M18 8l4 4-4 4" />
    </S>
  ),
  scripts: (p: P) => (
    <S {...p}>
      <path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" />
      <path d="M14 2v5h5M8 13h8M8 17h6" />
    </S>
  ),
  videos: (p: P) => (
    <S {...p}>
      <rect x="2" y="5" width="14" height="14" rx="2" />
      <path d="m16 9 6-3v12l-6-3" />
    </S>
  ),
  youtube: (p: P) => (
    <S {...p}>
      <rect x="2" y="5" width="20" height="14" rx="4" />
      <path d="m10 9 5 3-5 3V9Z" fill="currentColor" />
    </S>
  ),
  bell: (p: P) => (
    <S {...p}>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.7 21a2 2 0 0 1-3.4 0" />
    </S>
  ),
  logs: (p: P) => (
    <S {...p}>
      <path d="M4 6h16M4 12h16M4 18h10" />
    </S>
  ),
  settings: (p: P) => (
    <S {...p}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </S>
  ),
  wizard: (p: P) => (
    <S {...p}>
      <path d="m5 3 1.5 3L10 7.5 6.5 9 5 12 3.5 9 0 7.5 3.5 6 5 3Z" transform="translate(3 1) scale(.8)" />
      <path d="M15 6 21 12M9 12l3 3-7 7H2v-3l7-7Z" />
    </S>
  ),
  dollar: (p: P) => (
    <S {...p}>
      <path d="M12 2v20M17 6.5C17 4.6 14.8 3 12 3S7 4.6 7 6.5 9.2 10 12 10s5 1.6 5 3.5S14.8 17 12 17s-5-1.6-5-3.5" />
    </S>
  ),
  gauge: (p: P) => (
    <S {...p}>
      <path d="M12 14 8 8M3.3 15a9 9 0 1 1 17.4 0" />
      <circle cx="12" cy="14" r="1.6" fill="currentColor" />
    </S>
  ),
  check: (p: P) => (
    <S {...p}>
      <path d="M20 6 9 17l-5-5" />
    </S>
  ),
  spark: (p: P) => (
    <S {...p}>
      <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8Z" />
    </S>
  ),
  film: (p: P) => (
    <S {...p}>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M7 3v18M17 3v18M3 8h4M3 16h4M17 8h4M17 16h4M7 12h10" />
    </S>
  ),
};

export type IconName = keyof typeof Icon;

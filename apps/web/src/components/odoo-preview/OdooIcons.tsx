/** Tiny inline icons for the Odoo form preview (decorative, aria-hidden). */
type IconProps = { className?: string };

function Svg({ className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      className={className ?? "ofp-icon"}
      viewBox="0 0 16 16"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const CaretIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4.5 6.5 8 10l3.5-3.5" />
  </Svg>
);
export const ExternalIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9 3h4v4M13 3 7.5 8.5M11.5 9.5V13H3V4.5h3.5" />
  </Svg>
);
export const CalendarIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
    <path d="M2.5 6.5h11M5.5 2v3M10.5 2v3" />
  </Svg>
);
export const GearIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="8" cy="8" r="2.2" />
    <path d="M8 1.8v1.6M8 12.6v1.6M1.8 8h1.6M12.6 8h1.6M3.6 3.6l1.1 1.1M11.3 11.3l1.1 1.1M3.6 12.4l1.1-1.1M11.3 4.7l1.1-1.1" />
  </Svg>
);
export const ChevronLeftIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 3.5 5.5 8 10 12.5" />
  </Svg>
);
export const ChevronRightIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 3.5 10.5 8 6 12.5" />
  </Svg>
);
export const PaperclipIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10.5 5 6 9.5a1.4 1.4 0 0 0 2 2l4.6-4.6a2.8 2.8 0 0 0-4-4L3.9 7.6a4.2 4.2 0 0 0 6 6L13 10.5" />
  </Svg>
);
export const UserIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="8" cy="5.5" r="2.5" />
    <path d="M3 13.5c.6-2.4 2.6-3.8 5-3.8s4.4 1.4 5 3.8" />
  </Svg>
);
export const BoxIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M2.5 5 8 2.5 13.5 5v6L8 13.5 2.5 11z" />
    <path d="M2.5 5 8 7.5 13.5 5M8 7.5v6" />
  </Svg>
);

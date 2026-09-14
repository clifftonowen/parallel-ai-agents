interface Props {
  /** Rendered size in px, square. */
  size?: number;
}

/** The UROP mark: a printer's registration mark, slightly out of register.
 *
 *  The crosshair-in-a-circle is what a press uses to check that its separate
 *  colour plates line up. Borrowed rather than invented, because the whole
 *  design system is a press sheet. It also says the right thing about this
 *  project: separate passes, run at the same time, that have to align into one
 *  result. The cyan plate sits up and left of the magenta one, so above favicon
 *  size you can see the registration is off, which is the honest version.
 *
 *  Inline rather than <img src="/mark.svg"> — and that is not a preference.
 *  An SVG loaded through <img> is a separate document: it cannot see the
 *  page's custom properties, and a prefers-color-scheme rule inside it would
 *  follow the OS rather than this app. That exact trap already bit once, when
 *  the mark turned paper-coloured on a paper-coloured page in dark-mode
 *  Chrome. Inlined, the key plate is currentColor and simply inherits.
 *
 *  public/favicon.svg keeps its own media query and is correct as it stands,
 *  because the browser tab strip really does follow the OS.
 *
 *  Stroke width is 4 on a 64 unit grid so it lands on a whole pixel at 16px.
 *  An earlier version used 2.5, which is 0.6px in a browser tab and rendered
 *  as a grey smudge.
 */
export default function Mark({ size = 22 }: Props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      role="img"
      aria-label="UROP"
      style={{ display: "block", flex: "none" }}
    >
      <g fill="none" strokeWidth="4" strokeLinecap="butt">
        {/* cyan plate, off up and left */}
        <circle cx="30.5" cy="30.5" r="14" stroke="var(--color-accent)" opacity="0.85" />
        {/* magenta plate, off down and right */}
        <circle cx="33.5" cy="33.5" r="14" stroke="var(--color-accent-2)" opacity="0.85" />
        {/* the key plate, in register, carrying the crosshair */}
        <g stroke="currentColor">
          <circle cx="32" cy="32" r="14" />
          <path d="M32 4 V20 M32 44 V60 M4 32 H20 M44 32 H60" />
        </g>
      </g>
    </svg>
  );
}

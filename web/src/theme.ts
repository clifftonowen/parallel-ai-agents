// ── UROP — design tokens ────────────────────────────────────────────────────
// Ported from the "broadsheet" design system (Claude Design project
// bd8c5ad0-ee8d-424b-b8d0-ce82b34ccebf, _ds/broadsheet-.../styles.css).
//
// A press sheet, not a warm worksheet: cool grey ground, one serif doing every
// job, and the two process inks — cyan and magenta — carrying all the colour.
// Near-square corners and real shadows, so surfaces lift off the page rather
// than being drawn onto it.
//
// These names are mirrored as CSS custom properties in index.css. Inline
// styles read them from here; the component classes (.btn, .card, .seg …) read
// them from there. Change a value in BOTH or they drift.

export const c = {
  // Ground and surfaces.
  paper: "#f3f2f2", // --color-bg
  paperDeep: "#e0dede",
  paperCard: "#eae9e9", // --color-surface

  // Ink.
  ink: "#201e1d", // --color-text
  inkSoft: "#605d5d", // neutral-700
  inkFaint: "#7d7979", // neutral-600

  // Rules. The system draws divisions with hairlines, not boxes.
  rule: "#d7d3d3", // neutral-300
  ruleSoft: "#eae7e7", // neutral-200

  // First process ink: cyan. Actions and live state.
  // `reagent*` keeps the old names so the call sites did not have to churn
  // twice in one week; read it as "the accent".
  reagent: "#0088b0", // --color-accent
  reagentSoft: "#38a6cf", // accent-500
  reagentWash: "#e9f8ff", // accent-100
  reagentDeep: "#006786", // accent-700, for text on the pale ground

  // Second process ink: magenta. Attention and failure only.
  flag: "#d6006c", // --color-accent-2
  flagWash: "#fff1f4", // accent-2-100
  flagDeep: "#aa0b56", // accent-2-700

  // Third ink, print treatments only (see .cmyk-num in index.css). Never
  // chrome, never body copy.
  processYellow: "#edbb00",
} as const;

/** Tonal ramps, for the places that need a step rather than a role. */
export const neutral = {
  100: "#f8f4f4", 200: "#eae7e7", 300: "#d7d3d3", 400: "#bab6b6", 500: "#9b9797",
  600: "#7d7979", 700: "#605d5d", 800: "#444141", 900: "#2d2b2b",
} as const;

export const accent = {
  100: "#e9f8ff", 200: "#cbeeff", 300: "#99e0ff", 400: "#62c5ee", 500: "#38a6cf",
  600: "#1186ac", 700: "#006786", 800: "#004961", 900: "#0a303e",
} as const;

// ── The accent rule ─────────────────────────────────────────────────────────
// Cyan marks two things and nothing else:
//   1. ACTION or STATE — the primary action, or whatever is running. A list of
//      equivalent actions (one Download per file) counts as one use.
//   2. ONE editorial accent per screen.
// Magenta is failure and attention, never decoration. Everything else is ink.
// If something needs to stand out and is neither, it wants weight or space.

// ── Type ────────────────────────────────────────────────────────────────────
// One family in every role. The system carries its personality through weight,
// size and italic rather than through a second or third typeface, so there is
// no separate display or label face. Mono survives for one job only: the run
// log and file names, where character alignment is the point.
export const font = {
  display: "'Source Serif 4', Georgia, serif",
  body: "'Source Serif 4', Georgia, serif",
  mono: "'Space Mono', 'Cascadia Code', 'Consolas', monospace",
} as const;

/** Broadsheet's heading ramp: body 15, h6 13, h4 20, h3 25, h2 32, h1 42. */
export const size = {
  micro: 11, // tags, table units, meta
  small: 13, // captions, card body, h6
  body: 15, // default UI text
  lead: 17, // intro copy, card titles
  title: 20, // h4, section headings
  head: 25, // h3, page headings
  hero: 32, // h2, stat figures
} as const;

// The page heading is fluid; everything else picks a fixed step.
export const display = "clamp(32px, 5vw, 42px)";
export const displaySmall = "clamp(22px, 3.4vw, 28px)";

/** Weight for headings. The serif is only loaded at 400 and 600. */
export const headingWeight = 600;

// ── Spacing ─────────────────────────────────────────────────────────────────
// Broadsheet's 5px ramp. Its stylesheet defines only 1,2,3,4,6,8 while its own
// markup uses --space-5 and --space-7, which therefore resolved to nothing;
// the full ramp is filled in here and in index.css.
export const space = {
  xs: 5, // --space-1
  sm: 10, // --space-2
  md: 15, // --space-3
  base: 20, // --space-4
  lg: 25, // --space-5  (was missing upstream)
  xl: 30, // --space-6
  xxl: 35, // --space-7  (was missing upstream)
  section: 40, // --space-8
  page: 60,
} as const;

export const radius = { sm: 1, md: 2, lg: 4 } as const;

export const shadow = {
  sm: "0 1px 2px color-mix(in srgb, #2d2b2b 14%, transparent)",
  md: "0 3px 10px color-mix(in srgb, #2d2b2b 16%, transparent)",
  lg: "0 12px 32px color-mix(in srgb, #2d2b2b 22%, transparent)",
} as const;

// ── Layout ──────────────────────────────────────────────────────────────────
export const layout = {
  sidebar: 264, // the fixed left rail
  shell: 980, // main content column
  measure: "62ch", // prose blocks: a CSS length, so it drops straight into maxWidth
  narrow: 440, // sign-in and other single-purpose forms
  gutter: 40, // --space-8, the main pane's horizontal padding
} as const;

/** The recurring structural label: small, tracked, uppercase, in the serif. */
export const eyebrow: React.CSSProperties = {
  fontFamily: font.body,
  fontSize: size.micro,
  fontWeight: headingWeight,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: c.inkFaint,
};

/** Muted body text, the design's most-repeated colour treatment. */
export const muted = "color-mix(in srgb, #201e1d 62%, transparent)";
export const mutedFaint = "color-mix(in srgb, #201e1d 48%, transparent)";

export const hairline = `1px solid ${c.rule}`;
export const hairlineSoft = `1px solid ${c.ruleSoft}`;

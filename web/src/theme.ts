// ── UROP — design tokens ────────────────────────────────────────────────────
// Ported from the "broadsheet" design system (Claude Design project
// bd8c5ad0-ee8d-424b-b8d0-ce82b34ccebf, _ds/broadsheet-.../styles.css).
//
// ── One source of truth ─────────────────────────────────────────────────────
// The colour tokens below are `var(--token)` references, not literals. The real
// values live in index.css and nowhere else.
//
// This file used to hold hex and index.css held the same hex again, with a
// comment telling you to change both. They had already drifted: paperDeep,
// reagentSoft, accent 300/400/500/900 and space.page existed only here, while
// --color-divider and --color-accent-2-800 existed only there. The visible
// symptom was two slightly different hairlines on screen at once, because
// inline styles ruled at neutral-300 and .btn/.input/.table ruled at
// --color-divider.
//
// Colours, borders, shadows and the muted text mixes resolve through CSS.
// `space`, `size`, `radius` and `layout` stay NUMBERS, because call sites do
// arithmetic on them and template them into compound values. "var(--space-1)px"
// is not valid CSS and would fail silently.

export const c = {
  // Ground and surfaces.
  paper: "var(--color-bg)",
  paperDeep: "var(--color-bg-deep)",
  paperCard: "var(--color-surface)",

  // Ink.
  ink: "var(--color-text)",
  inkSoft: "var(--color-neutral-700)",
  inkFaint: "var(--color-neutral-600)",

  // Rules. The system draws divisions with hairlines, not boxes.
  rule: "var(--color-neutral-300)",
  ruleSoft: "var(--color-neutral-200)",

  // First process ink: cyan. Actions and live state.
  // `reagent*` keeps the old names so the call sites did not have to churn
  // twice in one week; read it as "the accent".
  reagent: "var(--color-accent)",
  reagentSoft: "var(--color-accent-500)",
  reagentWash: "var(--color-accent-100)",
  reagentDeep: "var(--color-accent-700)",

  // Second process ink: magenta. Attention and failure only.
  flag: "var(--color-accent-2)",
  flagWash: "var(--color-accent-2-100)",
  flagDeep: "var(--color-accent-2-700)",

  // Third ink, print treatments only (see .cmyk-num in index.css). Never
  // chrome, never body copy.
  processYellow: "var(--color-process-yellow)",
} as const;

/** Tonal ramps, for the places that need a step rather than a role. */
export const neutral = {
  100: "var(--color-neutral-100)", 200: "var(--color-neutral-200)",
  300: "var(--color-neutral-300)", 400: "var(--color-neutral-400)",
  500: "var(--color-neutral-500)", 600: "var(--color-neutral-600)",
  700: "var(--color-neutral-700)", 800: "var(--color-neutral-800)",
  900: "var(--color-neutral-900)",
} as const;

export const accent = {
  100: "var(--color-accent-100)", 200: "var(--color-accent-200)",
  300: "var(--color-accent-300)", 400: "var(--color-accent-400)",
  500: "var(--color-accent-500)", 600: "var(--color-accent-600)",
  700: "var(--color-accent-700)", 800: "var(--color-accent-800)",
  900: "var(--color-accent-900)",
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
  display: "var(--font-heading)",
  body: "var(--font-body)",
  mono: "var(--font-mono)",
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
  sm: "var(--shadow-sm)",
  md: "var(--shadow-md)",
  lg: "var(--shadow-lg)",
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
export const muted = "color-mix(in srgb, var(--color-text) 62%, transparent)";
export const mutedFaint = "color-mix(in srgb, var(--color-text) 48%, transparent)";

export const hairline = `1px solid ${c.rule}`;
export const hairlineSoft = `1px solid ${c.ruleSoft}`;

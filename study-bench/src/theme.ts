// ── The Study Bench — design tokens ─────────────────────────────────────────
// A warm lab-worksheet ground. Ink on paper, chunked by hairline rules, with a
// single accent bound to STATE.
//
// This file is the whole visual system. Every colour, size and gap in either
// app should come from here, so a later redesign is a change to this file
// rather than a sweep through forty style objects.
//
// Kept BYTE-IDENTICAL with study-bench/src/theme.ts. The two drifted once
// already; `diff` returning nothing is the check.

export const c = {
  // Ground and surfaces. paper and paperCard were previously two shades of the
  // same cream ~2% apart, which made every input and card invisible against
  // the page. The ground is now deeper so raised surfaces actually read.
  paper: "#EDE7D9",
  paperDeep: "#E0D8C5",
  paperCard: "#F7F3EA",
  ink: "#17150F",
  inkSoft: "#5A5341",
  inkFaint: "#8A8069",
  rule: "#C6BCA5",
  ruleSoft: "#D8CFBB",
  reagent: "#1F6F5C", // viridian — see the accent rule below
  reagentSoft: "#3E9079",
  reagentWash: "#DCE8E1",
  flag: "#B5451F", // vermilion — error / attention only
  flagWash: "#F0DCD2",
} as const;

// ── The accent rule ────────────────────────────────────────────────────────
// Viridian earns attention only if it is rare. It marks exactly two things:
//   1. ACTION or STATE — the primary action, or whatever is currently
//      running. A list of equivalent primary actions (one Download per file,
//      one Read per material) counts as one use, because it is one idea.
//   2. ONE editorial accent in the display heading, and only one.
// Nav links, section labels, field labels and secondary controls are ink.
// If something needs to stand out and is neither of the above, it wants
// weight or space, not colour.
//
// The previous version of this comment claimed the accent appeared "only
// where something is reacting", while the home page used it on six static
// elements. A rule the code does not follow is worse than no rule, so if you
// break this one, change this paragraph too.

export const font = {
  display: "'Fraunces', Georgia, serif",
  body: "'Inter', system-ui, sans-serif",
  mono: "'Space Mono', 'Cascadia Code', monospace",
} as const;

// ── Type scale ─────────────────────────────────────────────────────────────
// Seven steps. Replaces 25 ad-hoc inline sizes that included neighbours 0.5px
// apart, which no reader can perceive and no maintainer can choose between.
// Pick the nearest step; if two steps feel equally wrong the fix is usually
// weight or colour, not a new size.
export const size = {
  micro: 11, // mono eyebrows, table units
  small: 12, // captions, metadata
  body: 14, // default UI text
  lead: 16, // intro paragraphs, list items
  title: 20, // card and section titles
  head: 26, // page headings
  hero: 34, // the display heading floor (see `display` for the fluid version)
} as const;

// Display headings are fluid rather than fixed steps: they are the one place
// the layout is allowed to breathe with the viewport. Two tiers only —
// `display` for the heading that names the page, `displaySmall` for panel and
// single-purpose-form headings. There were five slightly different clamps
// before, which is four more than the hierarchy has levels.
export const display = "clamp(34px, 6vw, 56px)";
export const displaySmall = "clamp(24px, 4vw, 34px)";

// ── Spacing scale ──────────────────────────────────────────────────────────
// One 4px-based ramp. Vertical rhythm comes from picking neighbouring steps,
// not from typing another number.
export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
  section: 64,
  page: 96,
} as const;

// ── Layout ─────────────────────────────────────────────────────────────────
// There was previously one container width per file: 900, 820, 800, 760, 680,
// 640, 520 and 460 all coexisted, and the app header was wider than every page
// beneath it — so the wordmark hung to the left of the content on every
// screen. Two widths now, and the header shares `shell` so the left edges line
// up.
export const layout = {
  shell: 760, // every page and the app header — the one alignment
  measure: 560, // prose blocks: intro copy, empty states, help text
  narrow: 460, // sign-in and other single-purpose forms
  gutter: 22, // horizontal page padding
} as const;

// A wide-tracked, small-caps mono eyebrow — the recurring structural label.
export const eyebrow: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  fontWeight: 700,
  letterSpacing: "0.22em",
  textTransform: "uppercase",
  color: c.inkFaint,
};

// Hairline rule used to chunk the worksheet.
export const hairline = `1px solid ${c.rule}`;
export const hairlineSoft = `1px solid ${c.ruleSoft}`;

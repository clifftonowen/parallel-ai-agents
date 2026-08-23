// ── The Study Bench — design tokens ─────────────────────────────────────────
// A warm lab-worksheet ground. The single accent (reagent viridian) is bound to
// STATE — it appears only where something is "reacting" (running). Everything
// else is ink on paper, chunked by hairline rules.
// Shared with study-bench/src/theme.ts so the two apps read as one product.

export const c = {
  paper: "#F1ECE0",
  paperDeep: "#E4DCCB",
  paperCard: "#F7F3EA",
  ink: "#17150F",
  inkSoft: "#5A5341",
  inkFaint: "#8A8069",
  rule: "#C6BCA5",
  ruleSoft: "#D8CFBB",
  reagent: "#1F6F5C", // viridian — live / active only
  reagentSoft: "#3E9079",
  reagentWash: "#DCE8E1",
  flag: "#B5451F", // vermilion — error / attention only
  flagWash: "#F0DCD2",
} as const;

export const font = {
  display: "'Fraunces', Georgia, serif",
  body: "'Inter', system-ui, sans-serif",
  mono: "'Space Mono', 'Cascadia Code', monospace",
} as const;

// A wide-tracked, small-caps mono eyebrow — the recurring structural label.
export const eyebrow: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.22em",
  textTransform: "uppercase",
  color: c.inkFaint,
};

// Hairline rule used to chunk the worksheet.
export const hairline = `1px solid ${c.rule}`;
export const hairlineSoft = `1px solid ${c.ruleSoft}`;

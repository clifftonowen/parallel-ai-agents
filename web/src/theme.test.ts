// theme.ts holds var() references; index.css holds the values. This test is
// what keeps that arrangement honest.
//
// It exists because the failure mode is silent. An unresolvable custom property
// in an inline style is invalid at computed-value time: React sets it, the
// browser drops the declaration, and you get an element with no background
// rather than an error. No console warning, no TypeScript complaint, no failed
// build. Across ~180 style objects a single typo would ship as "looks slightly
// off" and be very hard to trace back.
//
// Before this, the two files held the same hex twice with a comment asking you
// to change both. They had drifted: paperDeep, reagentSoft and accent
// 300/400/500/900 existed only in TS, --color-divider and --color-accent-2-800
// only in CSS, and inline rules drew at neutral-300 while .btn/.input/.table
// drew at --color-divider, so two different hairlines were on screen at once.

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const here = join(process.cwd(), "src");

/**
 * Comments have to go first. Both files explain this token arrangement in
 * prose, and that prose names `var(--token)` and `--space-2`, which a naive
 * scan happily reports as a missing token.
 */
function code(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
}

const css = code(readFileSync(join(here, "index.css"), "utf8"));
const rawTs = readFileSync(join(here, "theme.ts"), "utf8");
const ts = code(rawTs);

/** Every `--name:` declared anywhere in the stylesheet. */
function declared(source: string): Set<string> {
  return new Set(
    [...source.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]),
  );
}

/** Every `var(--name)` reached for. */
function referenced(source: string): Set<string> {
  return new Set(
    [...source.matchAll(/var\(\s*(--[a-z0-9-]+)/g)].map((m) => m[1]),
  );
}

describe("design tokens", () => {
  it("resolves every var() theme.ts reaches for", () => {
    const missing = [...referenced(ts)].filter((n) => !declared(css).has(n));
    expect(missing, `declared in neither :root nor a scope block of index.css`)
      .toEqual([]);
  });

  it("resolves every var() index.css reaches for", () => {
    // Same guard for the stylesheet's own internal references, so a renamed
    // token cannot half-land.
    const missing = [...referenced(css)].filter((n) => !declared(css).has(n));
    expect(missing).toEqual([]);
  });

  it("keeps colour values out of theme.ts", () => {
    // The whole point. A hex literal here means the value exists in two places
    // again and the drift this test guards against can restart.
    expect(ts.match(/#[0-9a-fA-F]{3,8}\b/g) ?? []).toEqual([]);
  });

  it("keeps the numeric ramps as numbers", () => {
    // space/size/radius get templated into compound values as `${x}px`, so a
    // var() here would produce "var(--space-2)px" and silently drop.
    for (const name of ["space", "size", "radius"]) {
      const block = ts.match(
        new RegExp(`export const ${name} = \\{[\\s\\S]*?\\} as const;`),
      );
      expect(block, `${name} block not found`).toBeTruthy();
      expect(block![0]).not.toContain("var(");
    }
  });
});

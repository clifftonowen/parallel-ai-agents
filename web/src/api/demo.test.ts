import { describe, expect, it } from "vitest";
import * as demo from "./demo";
import { hasBenchmarkData } from "../types";

/**
 * The demo fixture is what a visitor with no backend actually sees, and every
 * piece of it is compiled in at build time. So the failure mode this guards
 * against is not a crash — it is a renamed field or a moved file turning into a
 * blank tab in production, which nothing else would catch.
 */
describe("demo fixture", () => {
  it("carries the real notes, not a placeholder", () => {
    const notes = demo.fileText("notes.md");
    expect(notes.length).toBeGreaterThan(1000);
    expect(notes).toContain("Binary Search");
    // The markdown starts with content. An earlier candidate run began with the
    // agent narrating its own tool failures, which is a poor first impression
    // and the reason this fixture was chosen over it.
    expect(notes.trimStart().startsWith("#")).toBe(true);
  });

  it("carries the real flashcards, in the format the parser expects", () => {
    const cards = demo.fileText("flashcards.md");
    expect(cards.length).toBeGreaterThan(1000);
    // parseFlashcards splits on --- and reads ## headings.
    expect(cards).toContain("##");
    expect(cards).toContain("---");
  });

  it("refuses a file it has no fixture for, rather than returning empty", () => {
    expect(() => demo.fileText("nope.md")).toThrow();
  });

  it("points every output at a static path under /demo/", () => {
    const outputs = demo.run().outputs;
    expect(Object.keys(outputs).sort()).toEqual([
      "flashcards_md",
      "flashcards_pdf",
      "notes_md",
      "notes_pdf",
      "video",
    ]);
    for (const name of Object.values(outputs)) {
      expect(demo.fileUrl(name!)).toBe(`/demo/${name}`);
    }
  });

  it("leaks no absolute filesystem path", () => {
    // A real run reports paths like C:\Users\...\output\<id>\notes.md. Those
    // say nothing useful here and describe somebody's machine.
    const blob = JSON.stringify(demo.run());
    expect(blob).not.toMatch(/[A-Za-z]:\\/);
    expect(blob).not.toContain("/output/");
  });

  it("reports the run as finished, at the time it actually ran", () => {
    const run = demo.run();
    expect(run.status).toBe("complete");
    expect(run.progress_pct).toBe(100);
    // Not "now": a demo claiming to have been generated on page load is a lie
    // about the artifact.
    expect(new Date(run.started_at).getFullYear()).toBe(2026);
    expect(new Date(run.started_at).getTime()).toBeLessThan(Date.now());
  });

  it("does not pretend the session has benchmark data", () => {
    // That run predates the profiling harness. Attaching the committed
    // comparison — a different topic, a different run — would be fabricating.
    expect(hasBenchmarkData(demo.run().benchmark)).toBe(false);
  });

  it("serves the committed benchmark report with all three arms readable", () => {
    const [first] = demo.benchmarks();
    expect(first.name).toBe("video-off-thread-vs-async");
    expect(hasBenchmarkData(first.report)).toBe(true);
    // The two arms this comparison exists to compare.
    expect(first.report.original?.total_wall_s).toBeGreaterThan(0);
    expect(first.report.async?.total_wall_s).toBeGreaterThan(0);
    // And the finding itself: asyncio is faster overall. If this ever flips,
    // the landing page's headline is wrong and should fail here first.
    expect(first.report.async!.total_wall_s).toBeLessThan(
      first.report.original!.total_wall_s,
    );
  });

  it("lists exactly the one session it has", () => {
    const runs = demo.runs();
    expect(runs).toHaveLength(1);
    expect(runs[0].run_id).toBe(demo.DEMO_RUN_ID);
    expect(runs[0].run_id).toBe(demo.run().run_id);
    expect(runs[0].topic).toBe(demo.run().topic);
  });

  it("says nobody is signed in and nobody may spend", () => {
    const access = demo.access();
    expect(access.can_run).toBe(false);
    expect(access.is_admin).toBe(false);
    expect(access.pending).toBe(false);
  });

  it("reports stats that match the fixture rather than flattering numbers", () => {
    const stats = demo.stats();
    expect(stats.runs_total).toBe(demo.runs().length);
    expect(stats.runs_complete).toBe(demo.runs().length);
    expect(stats.runs_active).toBe(0);
    expect(stats.cache.entries).toBe(0);
    expect(stats.cache.hits).toBe(0);
  });

  it("explains itself when something genuinely needs the backend", () => {
    const err = demo.unavailable("Starting a run");
    expect(err.message).toContain("Starting a run");
    expect(err.message).toContain("demo");
  });

  it("publishes no contact address unless one was configured", () => {
    // Building an address into a public page is a decision for whoever owns
    // it. Unset, the app points at the repository instead.
    expect(demo.CONTACT_EMAIL).toBeNull();
    expect(demo.REPO_URL).toMatch(/^https:\/\/github\.com\//);
  });
});

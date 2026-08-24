/**
 * The standalone demo.
 *
 * `VITE_DEMO_MODE=1` builds a version of this app that needs no backend at all:
 * a static host serves it and every page works. That is the whole point — the
 * pipeline behind this app spawns ten-to-thirty-minute subprocesses driving
 * ffmpeg, pandoc and Chromium, which no serverless platform will host, so the
 * front-end has to be shippable on its own or the link is dead.
 *
 * **Nothing here is invented.** Every artifact is the real output of one real
 * run of the pipeline (`binary search`, 2026-08-23 — the most recent complete
 * run in the tree, so it reflects how the pipeline behaves now), and the
 * benchmark numbers are the committed comparison in `benchmarks/`, imported
 * from that directory rather than copied, so there is still exactly one copy
 * of them in the repo.
 *
 * The notes carry six images the pipeline's own image_search tool found, still
 * pointing at the sites they came from. They are not rehosted: republishing
 * someone else's images under this domain would be a bigger problem than an
 * occasional broken hotlink, and a broken one degrades to its alt text.
 *
 * The one thing this cannot do is show that run's own benchmark: it predates
 * the profiling harness, so it has no report. The committed comparison is a
 * different topic and a different run, and attaching it to this session would
 * be fabricating a result. So the session carries `benchmark: null` and the
 * numbers stay on the Benchmark page where they belong.
 */
import curatedReport from "../../../benchmarks/video-off-thread-vs-async.json";
// From public/demo/ rather than a second copy under src/: the same files are
// served as static assets for the PDF and download paths, and two copies of a
// fixture drift.
import flashcardsMd from "../../public/demo/flashcards.md?raw";
import notesMd from "../../public/demo/notes.md?raw";
import type {
  AccessState, BenchmarkReport, CuratedBenchmark, RunState, RunSummary, Stats,
} from "../types";

/** Build-time flag. Vite inlines this, so the real client is tree-shaken out
 *  of a demo build and the fixtures out of a normal one. */
export const DEMO = import.meta.env.VITE_DEMO_MODE === "1";

/** The one run in the demo. A fixed id, so `/session/demo` is a shareable URL
 *  rather than a uuid nobody can type. */
export const DEMO_RUN_ID = "demo";

export const DEMO_TOPIC = "Binary search";

/** When the run actually happened. Not "now" — a demo that claims to have been
 *  generated the moment you loaded the page is a lie about the artifact. */
const RAN_AT = "2026-08-23T09:30:12.973Z";

/** Static paths under web/public/demo/, served by any host without a backend.
 *  Deliberately not the absolute filesystem paths a real run reports: those
 *  leak the machine's directory layout and mean nothing here. */
const FILES = {
  notes_md: "notes.md",
  flashcards_md: "flashcards.md",
  notes_pdf: "notes.pdf",
  flashcards_pdf: "flashcards.pdf",
  video: "study_video.mp4",
} as const;

export function fileUrl(filename: string): string {
  return `/demo/${filename}`;
}

/** The markdown, compiled into the bundle rather than fetched.
 *
 *  `fetchFileText` would work against /demo/*.md too, but importing means a
 *  missing fixture is a build failure instead of a blank tab in production.
 */
export function fileText(filename: string): string {
  if (filename === FILES.notes_md) return notesMd;
  if (filename === FILES.flashcards_md) return flashcardsMd;
  throw new Error(`No demo fixture for ${filename}.`);
}

export function run(): RunState {
  return {
    run_id: DEMO_RUN_ID,
    topic: DEMO_TOPIC,
    started_at: RAN_AT,
    status: "complete",
    phase: "done",
    progress_pct: 100,
    log_lines: [],
    outputs: { ...FILES },
    error: null,
    mode: "async",
    // See the note at the top: this run predates the profiling harness.
    benchmark: null,
  };
}

export function runs(): RunSummary[] {
  return [
    {
      run_id: DEMO_RUN_ID,
      topic: DEMO_TOPIC,
      status: "complete",
      started_at: RAN_AT,
      progress_pct: 100,
      phase: "done",
      mode: "async",
    },
  ];
}

export function benchmarks(): CuratedBenchmark[] {
  return [
    {
      name: "video-off-thread-vs-async",
      report: curatedReport as unknown as BenchmarkReport,
    },
  ];
}

/** Sidebar meters. One finished run, and a cache that never ran, stated as
 *  zero rather than dressed up. */
export function stats(): Stats {
  return {
    runs_total: 1,
    runs_complete: 1,
    runs_active: 0,
    runs_today: 0,
    // 0 means "no limit" everywhere else in the app, which is also the honest
    // answer here: there is no server to enforce one against.
    runs_daily_limit: 0,
    runs_concurrent_limit: 0,
    cache: { entries: 0, hits: 0 },
  };
}

/** Nobody is signed in and nobody can run anything: there is no server to sign
 *  in to or spend against. The UI reads these to explain itself rather than to
 *  offer a button that cannot work. */
export function access(): AccessState {
  return { can_run: false, pending: false, requested_at: null, is_admin: false };
}

/** Thrown by any client call that genuinely needs a backend. Reaching one of
 *  these is a bug in the UI's demo handling, not something a visitor should
 *  ever see, so it says so plainly. */
export function unavailable(what: string): Error {
  return new Error(
    `${what} needs the live backend. This is the standalone demo build.`,
  );
}

/** Where to point somebody who wants to see it run for real. An address is
 *  only published if whoever owns it set VITE_CONTACT_EMAIL; otherwise this is
 *  the repository, which is public anyway. */
export const REPO_URL = "https://github.com/clifftonowen/parallel-ai-agents";

export const CONTACT_EMAIL: string | null =
  import.meta.env.VITE_CONTACT_EMAIL?.trim() || null;

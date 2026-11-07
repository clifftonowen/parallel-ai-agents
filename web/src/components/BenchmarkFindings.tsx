import PlateNumber from "./PlateNumber";
import sweep from "../../../benchmarks/assembly-sweep.json";
import orchestration from "../../../benchmarks/thread-vs-async-n5.json";
import {
  c, eyebrow, font, hairline, headingWeight, layout, muted, mutedFaint, size,
  space,
} from "../theme";

/**
 * The two results, read from the committed artifacts rather than retyped.
 *
 * These are summaries across repeated runs, not per-run reports, which is why
 * they are imported at build time instead of coming from `/benchmarks`. That
 * endpoint serves individual profiling reports and the charts below render
 * those; these numbers only change when the experiment is re-run and new
 * results are committed.
 */

const A = orchestration.arms.original.total_wall_s;
const B = orchestration.arms.async.total_wall_s;
const seq = sweep.configs.sequential;
const par1 = sweep.configs.parallel_1;
const par7 = sweep.configs.parallel_7;

const WIDTHS: { label: string; cfg: { mean_s: number; stdev_s: number } }[] = [
  { label: "MoviePy, one encode", cfg: seq },
  { label: "1 ffmpeg, still serial", cfg: par1 },
  { label: "2 concurrent", cfg: sweep.configs.parallel_2 },
  { label: "4 concurrent", cfg: sweep.configs.parallel_4 },
  { label: "7 concurrent", cfg: par7 },
];

export default function BenchmarkFindings() {
  const preParallel = seq.mean_s / par1.mean_s;
  const total = seq.mean_s / par7.mean_s;
  const fromParallelism = par1.mean_s / par7.mean_s;

  return (
    <>
      {/* ── The one memorable number ───────────────────────────────────── */}
      <div style={figures}>
        <div>
          <PlateNumber value={`${total.toFixed(1)}×`} />
          <div style={figureLabel}>faster video assembly</div>
          <div style={figureNote}>
            the stage that is 75 to 81% of a full run
          </div>
        </div>
        <div>
          <PlateNumber value={`${Math.round((1 - 1 / preParallel) / (1 - 1 / total) * 100)}%`} />
          <div style={figureLabel}>of the speedup before parallelism</div>
          <div style={figureNote}>
            replacing MoviePy did most of the work
          </div>
        </div>
      </div>

      {/* ── Finding 1 ──────────────────────────────────────────────────── */}
      <section style={finding}>
        <span style={eyebrow}>Finding one</span>
        <h2 style={findingHead}>
          The coordination method made no measurable difference
        </h2>
        <p style={prose}>
          We ran each method five times with the same topic, with video and
          caching off. We alternated which method went first, so changes in API
          latency would not consistently favor one method.
        </p>

        <table className="table" style={{ maxWidth: 520 }}>
          <thead>
            <tr><th>arm</th><th>total wall</th><th>range</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>thread pool</td>
              <td>{A.mean_s.toFixed(1)}s ± {A.stdev_s.toFixed(1)}</td>
              <td style={dim}>{A.min_s.toFixed(1)} to {A.max_s.toFixed(1)}</td>
            </tr>
            <tr>
              <td>shared executor</td>
              <td>{B.mean_s.toFixed(1)}s ± {B.stdev_s.toFixed(1)}</td>
              <td style={dim}>{B.min_s.toFixed(1)} to {B.max_s.toFixed(1)}</td>
            </tr>
          </tbody>
        </table>

        <p style={prose}>
          The overall ratio was {orchestration.speedup_overall.toFixed(3)}×.
          Welch's t was 0.51 on about 8 degrees of freedom, and the gap was
          half a standard error. With five runs per method, this test could
          only resolve a difference of roughly 11 seconds. We measured 2.9.
        </p>

        <blockquote style={correction}>
          <p style={{ margin: 0 }}>
            An earlier version of this page claimed a 1.18× overall speedup and
            1.44× in phase 2, based on one run per method. Those results did not
            hold up. The variation between runs was about three times the
            claimed effect, and another single run came out the other way.
          </p>
          <footer style={correctionFoot}>
            The old phase figure used the longest component time. That left out
            the coordination overhead we wanted to compare. Both methods now
            time each whole phase.
          </footer>
        </blockquote>
      </section>

      {/* ── Finding 2 ──────────────────────────────────────────────────── */}
      <section style={finding}>
        <span style={eyebrow}>Finding two</span>
        <h2 style={findingHead}>
          Video assembly took most of the time
        </h2>
        <p style={prose}>
          Video assembly took 75 to 81% of the time in every recorded full
          run. Earlier benchmarks skipped that step. We measured it separately
          using a {sweep.slides} slide deck already on disk, so no model was called:
        </p>

        <table className="table" style={{ maxWidth: 520 }}>
          <thead>
            <tr><th>configuration</th><th>wall</th><th>speedup</th></tr>
          </thead>
          <tbody>
            {WIDTHS.map((w) => (
              <tr key={w.label}>
                <td>{w.label}</td>
                <td>{w.cfg.mean_s.toFixed(1)}s ± {w.cfg.stdev_s.toFixed(1)}</td>
                <td style={dim}>
                  {w.cfg === seq ? "baseline" : `${(seq.mean_s / w.cfg.mean_s).toFixed(2)}×`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p style={prose}>
          Most of the gain came before any parallel work. Replacing MoviePy
          with one direct ffmpeg process per slide, still in sequence, was{" "}
          <strong style={strong}>{preParallel.toFixed(2)}×</strong> on its own.
          Running those processes together added another{" "}
          {fromParallelism.toFixed(2)}× and saturates by about four workers,
          because each ffmpeg is already multi-threaded.
        </p>
        <p style={prose}>
          MoviePy decoded and combined every frame in Python before encoding
          the video again, even though each scene was a static image. ffmpeg
          handled that work directly. The stages we could run in parallel made
          up about a fifth of a full run; slow video assembly took the rest.
        </p>
        <p style={note}>{sweep.correctness}</p>
      </section>
    </>
  );
}

// ── styles ──────────────────────────────────────────────────────────────────

const figures: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: space.section,
  margin: `${space.base}px 0 ${space.xl}px`,
};

const figureLabel: React.CSSProperties = {
  ...eyebrow,
  color: c.reagentDeep,
  marginTop: space.sm,
};

const figureNote: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: mutedFaint,
  maxWidth: "30ch",
  marginTop: space.xs,
};

const finding: React.CSSProperties = {
  paddingTop: space.xl,
  paddingBottom: space.xl,
  borderTop: hairline,
};

const findingHead: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.head,
  lineHeight: 1.15,
  margin: `${space.xs}px 0 ${space.md}px`,
  maxWidth: "26ch",
};

const prose: React.CSSProperties = {
  fontSize: size.body,
  lineHeight: 1.6,
  color: muted,
  maxWidth: layout.measure,
  margin: `0 0 ${space.md}px`,
};

const dim: React.CSSProperties = { color: mutedFaint };

const strong: React.CSSProperties = { color: c.ink, fontWeight: headingWeight };

const correction: React.CSSProperties = {
  margin: `${space.base}px 0 0`,
  padding: `${space.md}px 0 ${space.md}px ${space.base}px`,
  borderLeft: `3px solid ${c.flag}`,
  fontSize: size.body,
  lineHeight: 1.55,
  color: c.ink,
  maxWidth: layout.measure,
};

const correctionFoot: React.CSSProperties = {
  marginTop: space.sm,
  fontSize: size.small,
  fontStyle: "italic",
  color: muted,
};

const note: React.CSSProperties = {
  fontSize: size.small,
  lineHeight: 1.55,
  color: mutedFaint,
  maxWidth: layout.measure,
  margin: 0,
};

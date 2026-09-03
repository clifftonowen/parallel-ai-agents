import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { curatedBenchmarks, listRuns } from "../api/client";
import BarChart from "../components/BarChart";
import BenchmarkFindings from "../components/BenchmarkFindings";
import TokenTable from "../components/TokenTable";
import type { BenchmarkReport, CuratedBenchmark, RunSummary } from "../types";
import {
  c, display, eyebrow, font, hairline, headingWeight, layout, muted,
  mutedFaint, size, space,
} from "../theme";

function secs(v?: number) {
  return v != null ? `${v.toFixed(1)}s` : "n/a";
}
function num(v?: number) {
  return v != null ? v.toLocaleString() : "n/a";
}

function Report({ report }: { report: BenchmarkReport }) {
  const orig = report.original;
  const adk = report.adk;
  const asyn = report.async;

  const maxWall = Math.max(
    orig?.total_wall_s ?? 0, adk?.total_wall_s ?? 0, asyn?.total_wall_s ?? 0, 1
  );
  const maxPhase = Math.max(
    orig?.phases?.phase1_wall_s ?? 0, asyn?.phases?.phase1_wall_s ?? 0,
    orig?.phases?.phase2_wall_s ?? 0, asyn?.phases?.phase2_wall_s ?? 0,
    orig?.phases?.phase3_wall_s ?? 0, asyn?.phases?.phase3_wall_s ?? 0,
    adk?.phases?.phase1 ?? 0, adk?.phases?.phase2 ?? 0, adk?.phases?.phase3 ?? 0,
    1
  );

  const adkLlmEvents = adk?.tokens?.by_agent
    ? Object.values(adk.tokens.by_agent).reduce((s, a) => s + (a.llm_events ?? 0), 0)
    : undefined;

  return (
    <div style={{ marginBottom: space.page }}>
      <p style={sectionLabel}>Wall clock</p>
      <div style={chartBlock}>
        <BarChart label="Total end to end" original={orig?.total_wall_s} adk={adk?.total_wall_s} async={asyn?.total_wall_s} maxValue={maxWall} />
      </div>

      <p style={sectionLabel}>By phase</p>
      <div style={chartBlock}>
        <BarChart label="Phase 1: notes (sequential in all arms)" original={orig?.phases?.phase1_wall_s} adk={adk?.phases?.phase1} async={asyn?.phases?.phase1_wall_s} maxValue={maxPhase} />
        <BarChart label="Phase 2: the parallel fan-out" original={orig?.phases?.phase2_wall_s} adk={adk?.phases?.phase2} async={asyn?.phases?.phase2_wall_s} maxValue={maxPhase} />
        <BarChart label="Phase 3: flashcards PDF (sequential in all arms)" original={orig?.phases?.phase3_wall_s} adk={adk?.phases?.phase3} async={asyn?.phases?.phase3_wall_s} maxValue={maxPhase} />
      </div>

      <p style={sectionLabel}>Tokens</p>
      <TokenTable
        showAsync={asyn != null}
        rows={[
          { label: "Input tokens", original: num(orig?.tokens?.total_input), adk: num(adk?.tokens?.total_input), async: num(asyn?.tokens?.total_input) },
          { label: "Output tokens", original: num(orig?.tokens?.total_output), adk: num(adk?.tokens?.total_output), async: num(asyn?.tokens?.total_output) },
          { label: "LLM calls", original: num(orig?.tokens?.llm_calls), adk: num(adkLlmEvents), async: num(asyn?.tokens?.llm_calls) },
          { label: "LLM latency", original: secs(orig?.tokens?.llm_total_s), adk: secs(adk?.otel?.avg_llm_latency_s), async: secs(asyn?.tokens?.llm_total_s) },
          ...(asyn?.tokens?.cache_read_tokens != null
            ? [{ label: "Cache read tokens", original: "n/a", adk: "n/a", async: num(asyn.tokens.cache_read_tokens) }]
            : []),
        ]}
      />
    </div>
  );
}

export default function BenchmarkPage() {
  const [curated, setCurated] = useState<CuratedBenchmark[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([curatedBenchmarks(), listRuns().catch(() => [])])
      .then(([b, r]) => {
        setCurated(b);
        setRuns(r);
      })
      .catch(() => setCurated([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: muted }}>Loading benchmarks…</p>;

  return (
    <main style={page}>
      <span style={kicker}>Research output</span>
      <h1 style={heading}>Does concurrency actually help?</h1>
      <p style={intro}>
        The app is a workload for one question: does running a multi-agent
        pipeline in parallel actually pay, and if so how. Two experiments, both
        repeated rather than run once, and both reported here including the one
        that went the wrong way.
      </p>

      <BenchmarkFindings />

      {curated.length === 0 ? (
        <p style={{ color: muted }}>
          No curated benchmarks found in <code>benchmarks/</code>.
        </p>
      ) : (
        curated.map((b) => (
          <section key={b.name}>
            <div style={runHead}>
              <h2 style={runTitle}>{b.report.topic}</h2>
              <span style={runMeta}>{b.name}</span>
            </div>
            <Report report={b.report} />
          </section>
        ))
      )}

      <div style={caveat}>
        <p style={caveatTitle}>How much to trust these numbers</p>
        <p style={caveatBody}>
          Video assembly is single-threaded ffmpeg and takes 76 to 81% of wall
          time on a full run. On the full pipeline that swamps any difference
          between orchestrators, which is Amdahl's law doing what it does. These
          runs skip video so the part I actually changed becomes visible. They
          are also one run per arm, and the two arms made a different number of
          LLM calls, so the overall figure is indicative at best. Phase 2 is the
          number I would trust. The full write-up is in{" "}
          <code>benchmarks/README.md</code>.
        </p>
      </div>

      {runs.length > 0 && (
        <>
          <p style={sectionLabel}>Your runs</p>
          <p style={{ ...intro, marginBottom: space.base }}>
            Only runs started through <code>benchmark_profile.py</code> carry
            their own report.
          </p>
          <div style={runList}>
            {runs.slice(0, 8).map((r) => (
              <Link key={r.run_id} to={`/benchmark/${r.run_id}`} style={runRow}>
                <span style={{ flex: 1, minWidth: 0 }}>{r.topic}</span>
                <span style={runMeta}>{r.status}</span>
              </Link>
            ))}
          </div>
        </>
      )}
    </main>
  );
}

// ── styles ──────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: layout.shell };

const kicker: React.CSSProperties = {
  display: "block",
  fontSize: size.small,
  fontStyle: "italic",
  color: c.reagentDeep,
  marginBottom: space.sm,
};

const heading: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: display,
  lineHeight: 1.05,
  margin: `0 0 ${space.md}px`,
};

const intro: React.CSSProperties = {
  fontSize: size.lead,
  color: muted,
  maxWidth: layout.measure,
  margin: `0 0 ${space.section}px`,
};

const runHead: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: space.base,
  borderTop: hairline,
  paddingTop: space.md,
  marginBottom: space.lg,
};

const runTitle: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.head,
  margin: 0,
};

const runMeta: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: mutedFaint,
};

const sectionLabel: React.CSSProperties = {
  ...eyebrow,
  marginBottom: space.md,
};

const chartBlock: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: space.md,
  marginBottom: space.xl,
};

const caveat: React.CSSProperties = {
  borderLeft: `2px solid ${c.flag}`,
  paddingLeft: space.base,
  marginBottom: space.page,
  maxWidth: layout.measure,
};

const caveatTitle: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.lead,
  margin: `0 0 ${space.xs}px`,
};

const caveatBody: React.CSSProperties = {
  fontSize: size.body,
  color: muted,
  margin: 0,
};

const runList: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
};

const runRow: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: space.base,
  padding: `${space.md}px 0`,
  borderBottom: `1px solid ${c.ruleSoft}`,
  color: c.ink,
  textDecoration: "none",
};

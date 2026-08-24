import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { downloadZip, getRun } from "../api/client";
import BarChart from "../components/BarChart";
import FileCard from "../components/FileCard";
import TokenTable from "../components/TokenTable";
import { hasBenchmarkData } from "../types";
import type { AsyncMetrics, BenchmarkReport, RunState } from "../types";
import { c, font, hairline, layout, size } from "../theme";

type Tab = "benchmark" | "outputs" | "log";

const TABS: { key: Tab; label: string }[] = [
  { key: "benchmark", label: "Benchmark" },
  { key: "outputs", label: "Outputs" },
  { key: "log", label: "Log" },
];

function fmt(v?: number) {
  return v != null ? `${v.toFixed(1)}s` : "—";
}
function fmtN(v?: number) {
  return v != null ? v.toLocaleString() : "—";
}

// ─── Benchmark Tab ───────────────────────────────────────────────────────────

function BenchmarkTab({ report }: { report: BenchmarkReport }) {
  const orig = report.original;
  const adk  = report.adk;
  const asyn: AsyncMetrics | undefined = report.async;

  const adkSpeedup =
    orig && adk && adk.total_wall_s > 0
      ? (orig.total_wall_s / adk.total_wall_s).toFixed(2)
      : null;

  const asyncSpeedup =
    orig && asyn && asyn.total_wall_s > 0
      ? (orig.total_wall_s / asyn.total_wall_s).toFixed(2)
      : null;

  const parallelDetected = adk?.otel?.tool_parallelism?.parallel_detected ?? null;

  const maxWall = Math.max(
    orig?.total_wall_s ?? 0,
    adk?.total_wall_s ?? 0,
    asyn?.total_wall_s ?? 0,
    orig?.phases?.phase1_wall_s ?? 0,
    adk?.phases?.phase1 ?? 0,
    asyn?.phases?.phase1_wall_s ?? 0,
    orig?.phases?.phase2_wall_s ?? 0,
    adk?.phases?.phase2 ?? 0,
    asyn?.phases?.phase2_wall_s ?? 0,
    orig?.phases?.phase3_wall_s ?? 0,
    adk?.phases?.phase3 ?? 0,
    asyn?.phases?.phase3_wall_s ?? 0,
    1
  );

  const videoMax = Math.max(
    orig?.agents?.video?.total_s ?? 0,
    adk?.agents?.video?.total_s ?? 0,
    asyn?.agents?.video?.total_s ?? 0,
    1
  );

  const adkTotalLlmEvents = adk?.tokens?.by_agent
    ? Object.values(adk.tokens.by_agent).reduce((s, a) => s + (a.llm_events ?? 0), 0)
    : undefined;

  const showAsync = asyn != null;

  const tokenRows = [
    { label: "Input tokens",  original: fmtN(orig?.tokens?.total_input),  adk: fmtN(adk?.tokens?.total_input),  async: fmtN(asyn?.tokens?.total_input) },
    { label: "Output tokens", original: fmtN(orig?.tokens?.total_output), adk: fmtN(adk?.tokens?.total_output), async: fmtN(asyn?.tokens?.total_output) },
    { label: "LLM calls",     original: fmtN(orig?.tokens?.llm_calls),    adk: fmtN(adkTotalLlmEvents),         async: fmtN(asyn?.tokens?.llm_calls) },
    { label: "LLM latency",   original: fmt(orig?.tokens?.llm_total_s),   adk: fmt(adk?.otel?.avg_llm_latency_s), async: fmt(asyn?.tokens?.llm_total_s) },
    ...(showAsync && asyn?.tokens?.cache_read_tokens != null
      ? [{ label: "Cache read tokens", original: "—", adk: "—", async: fmtN(asyn?.tokens?.cache_read_tokens) }]
      : []),
  ];

  return (
    <div style={tabStyles.scroll}>
      {/* Speedup badges */}
      {(adkSpeedup || asyncSpeedup || parallelDetected != null) && (
        <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
          {adkSpeedup && (
            <div style={tabStyles.speedupBadge}>
              <div style={{ fontFamily: font.display, fontSize: size.hero, fontWeight: 600, color: c.reagent }}>{adkSpeedup}×</div>
              <div style={{ fontFamily: font.mono, fontSize: size.micro, color: c.inkSoft, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>ADK Speedup</div>
            </div>
          )}
          {asyncSpeedup && (
            <div style={tabStyles.speedupBadge}>
              <div style={{ fontFamily: font.display, fontSize: size.hero, fontWeight: 600, color: c.reagentSoft }}>{asyncSpeedup}×</div>
              <div style={{ fontFamily: font.mono, fontSize: size.micro, color: c.inkSoft, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>Async Speedup</div>
            </div>
          )}
          {parallelDetected != null && (
            <div
              style={{
                ...tabStyles.parallelBadge,
                backgroundColor: parallelDetected ? c.reagentWash : c.flagWash,
                border: `1px solid ${parallelDetected ? c.reagent : c.flag}`,
              }}
            >
              <span style={{ fontSize: size.lead }}>{parallelDetected ? "✓" : "✗"}</span>
              <span style={{ color: c.ink, fontWeight: 700, fontSize: size.small }}>
                {parallelDetected ? "Parallel tool dispatch" : "Serial tool dispatch"}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Wall-clock comparison */}
      <p style={tabStyles.sectionTitle}>Wall-Clock Times</p>
      <div style={tabStyles.chartBlock}>
        <BarChart label="Total end-to-end" original={orig?.total_wall_s} adk={adk?.total_wall_s} async={asyn?.total_wall_s} maxValue={maxWall} />
        <BarChart label="Phase 1 — Notes" original={orig?.phases?.phase1_wall_s} adk={adk?.phases?.phase1} async={asyn?.phases?.phase1_wall_s} maxValue={maxWall} />
        <BarChart label="Phase 2 — Flashcards + Video" original={orig?.phases?.phase2_wall_s} adk={adk?.phases?.phase2} async={asyn?.phases?.phase2_wall_s} maxValue={maxWall} />
        <BarChart label="Phase 3 — PDFs" original={orig?.phases?.phase3_wall_s} adk={adk?.phases?.phase3} async={asyn?.phases?.phase3_wall_s} maxValue={maxWall} />
      </div>

      {/* Video sub-phases */}
      {(orig?.agents?.video || adk?.agents?.video || asyn?.agents?.video) && (
        <>
          <p style={tabStyles.sectionTitle}>Video Sub-Phases</p>
          <div style={tabStyles.chartBlock}>
            <BarChart label="Stage A — narrations ‖ slides" original={orig?.agents?.video?.stage_a_s} adk={adk?.agents?.video?.stage_a_s} async={asyn?.agents?.video?.stage_a_s} maxValue={videoMax} />
            <BarChart label="Stage B+C — audio ‖ pptx" original={orig?.agents?.video?.stage_bc_s} adk={adk?.agents?.video?.stage_bc_s} async={asyn?.agents?.video?.stage_bc_s} maxValue={videoMax} />
            <BarChart label="Stage D — assemble" original={orig?.agents?.video?.assemble_s} adk={adk?.agents?.video?.assemble_s} async={asyn?.agents?.video?.assemble_s} maxValue={videoMax} />
          </div>
        </>
      )}

      {/* Token usage */}
      <p style={tabStyles.sectionTitle}>Token Usage</p>
      <TokenTable rows={tokenRows} showAsync={showAsync} />
    </div>
  );
}

// ─── Outputs Tab ─────────────────────────────────────────────────────────────

function OutputsTab({ runState }: { runState: RunState }) {
  const { run_id, outputs } = runState;

  const OUTPUT_CARDS: {
    key: keyof typeof outputs;
    label: string;
    icon: string;
    previewable?: boolean;
  }[] = [
    { key: "notes_md", label: "notes.md", icon: "📝", previewable: true },
    { key: "flashcards_md", label: "flashcards.md", icon: "🃏", previewable: true },
    { key: "notes_pdf", label: "notes.pdf", icon: "📄" },
    { key: "flashcards_pdf", label: "flashcards.pdf", icon: "📄" },
    { key: "video", label: "study_video.mp4", icon: "🎬" },
  ];

  const available = OUTPUT_CARDS.filter((card) => outputs[card.key] != null && outputs[card.key] !== "");

  return (
    <div style={tabStyles.scroll}>
      {available.length === 0 ? (
        <p style={{ color: c.inkFaint, textAlign: "center", padding: "24px 0" }}>
          No output files found for this run.
        </p>
      ) : (
        <>
          {available.map((card) => {
            const fullPath = outputs[card.key] as string;
            const filename = fullPath.split(/[\\/]/).pop() ?? card.label;
            return (
              <FileCard
                key={card.key}
                run_id={run_id}
                label={card.label}
                filename={filename}
                icon={card.icon}
                previewable={card.previewable}
              />
            );
          })}
          <button onClick={() => downloadZip(run_id)} style={tabStyles.downloadAllBtn}>
            ⬇  Download All as ZIP
          </button>
        </>
      )}
    </div>
  );
}

// ─── Log Tab ─────────────────────────────────────────────────────────────────

function LogTab({ lines }: { lines: string[] }) {
  return (
    <pre style={tabStyles.logPre}>
      {lines.length === 0 ? (
        <span style={{ color: c.inkFaint }}>No log output captured.</span>
      ) : (
        lines.join("\n")
      )}
    </pre>
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────

export default function ResultsPage() {
  const { run_id } = useParams<{ run_id?: string }>();
  const navigate = useNavigate();
  const [runState, setRunState] = useState<RunState | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("benchmark");

  useEffect(() => {
    if (!run_id) return;
    getRun(run_id)
      .then(setRunState)
      .catch((e: unknown) => setFetchError(e instanceof Error ? e.message : "Failed to load results"))
      .finally(() => setLoading(false));
  }, [run_id]);

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60, color: c.inkSoft }}>
        Loading results...
      </div>
    );
  }
  if (fetchError || !runState) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 60, color: c.flag }}>
        {fetchError ?? "No results found."}
      </div>
    );
  }

  const report = (runState.benchmark ?? null) as BenchmarkReport | null;

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <button onClick={() => navigate("/")} style={styles.backBtn}>← Home</button>
        <h1 style={styles.title}>{runState.topic}</h1>
      </div>

      {/* Tab bar */}
      <div style={styles.tabBar}>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              ...styles.tab,
              ...(activeTab === tab.key ? styles.tabActive : {}),
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={styles.tabContent}>
        {activeTab === "benchmark" &&
          (hasBenchmarkData(report) ? (
            <BenchmarkTab report={report} />
          ) : (
            <p style={{ color: c.inkFaint, textAlign: "center", padding: "24px 0" }}>
              No benchmark data available. Only runs using benchmark_profile.py produce this data.
            </p>
          ))}
        {activeTab === "outputs" && <OutputsTab runState={runState} />}
        {activeTab === "log" && <LogTab lines={runState.log_lines} />}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: layout.shell,
    margin: "0 auto",
    padding: "20px 20px 24px",
    display: "flex",
    flexDirection: "column",
    height: "calc(100vh - 52px)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 16,
  },
  backBtn: {
    fontFamily: font.mono,
    color: c.reagent,
    fontSize: size.small,
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    flexShrink: 0,
  },
  title: {
    fontFamily: font.display,
    fontSize: size.title,
    fontWeight: 600,
    color: c.ink,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  tabBar: {
    display: "flex",
    borderBottom: hairline,
    marginBottom: 16,
    gap: 4,
  },
  tab: {
    flex: 1,
    backgroundColor: "transparent",
    color: c.inkSoft,
    fontFamily: font.mono,
    fontSize: size.small,
    fontWeight: 700,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    padding: "10px 0",
    borderBottom: "2px solid transparent",
    marginBottom: -1,
  },
  tabActive: {
    color: c.reagent,
    borderBottom: `2px solid ${c.reagent}`,
  },
  tabContent: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
  },
};

const tabStyles: Record<string, React.CSSProperties> = {
  scroll: {
    flex: 1,
    overflowY: "auto",
    paddingBottom: 24,
  },
  sectionTitle: {
    fontFamily: font.mono,
    color: c.inkFaint,
    fontSize: size.micro,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    marginBottom: 10,
    marginTop: 22,
  },
  chartBlock: {
    backgroundColor: c.paperCard,
    border: hairline,
    padding: 16,
  },
  speedupBadge: {
    backgroundColor: c.paperCard,
    border: hairline,
    padding: "14px 24px",
    textAlign: "center",
  },
  parallelBadge: {
    padding: "14px 20px",
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  downloadAllBtn: {
    width: "100%",
    backgroundColor: c.reagent,
    color: c.paper,
    fontFamily: font.body,
    padding: "14px 0",
    fontSize: size.body,
    fontWeight: 600,
    marginTop: 12,
  },
  logPre: {
    flex: 1,
    backgroundColor: c.ink,
    padding: 14,
    overflow: "auto",
    color: c.paperDeep,
    fontFamily: font.mono,
    fontSize: size.micro,
    lineHeight: 1.65,
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
  },
};

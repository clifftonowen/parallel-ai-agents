// Types for the whole app: the learner-facing study package AND the benchmark
// comparison. These were two files in two apps (`study-bench/src/types.ts` and
// `dashboard2/src/types/index.ts`) that described the same API from opposite
// ends — one omitted every benchmark shape, the other omitted the cache and
// cancellation fields. Both halves are real, so this is their union.

export interface User {
  email: string;
}

export interface AuthResponse {
  token: string;
  email: string;
}

/** Which orchestrator to run. "all"/"both" run several in sequence. */
export type RunMode = "both" | "original" | "adk" | "async" | "all";

export type RunStatus = "running" | "complete" | "error" | "cancelled";

export type RunPhase =
  | "starting"
  | "phase1"
  | "phase2"
  | "phase3"
  | "profiling"
  | "done"
  | "error";

// ─── Benchmark JSON shape (from benchmark_profile.py) ───────────────────────

export interface VideoAgentMetrics {
  total_s: number;
  stage_a_s: number;
  stage_bc_s: number;
  assemble_s: number;
}

export interface AgentTiming {
  duration_s?: number;
  started_at?: string;
  finished_at?: string;
}

export interface OriginalAgents {
  notes: AgentTiming;
  flashcard: AgentTiming;
  video: VideoAgentMetrics;
  notes_pdf: AgentTiming;
  flashcards_pdf: AgentTiming;
}

export interface OriginalPhases {
  phase1_wall_s: number;
  phase2_wall_s: number;
  phase3_wall_s: number;
}

export interface TokenMetrics {
  total_input: number;
  total_output: number;
  llm_calls?: number;
  llm_total_s?: number;
}

export interface OrchestratorMetrics {
  total_wall_s: number;
  phases: OriginalPhases;
  agents: OriginalAgents;
  tokens: TokenMetrics;
}

export interface ADKAgentTokens {
  input_tokens: number;
  output_tokens: number;
  llm_events: number;
}

export interface ADKAgents {
  notes?: ADKAgentTokens;
  flashcard?: ADKAgentTokens;
  video?: VideoAgentMetrics;
  notes_pdf?: ADKAgentTokens;
  flashcards_pdf?: ADKAgentTokens;
}

export interface ADKPhases {
  phase1?: number;
  phase2?: number;
  phase3?: number;
}

export interface ADKTokenMetrics {
  total_input: number;
  total_output: number;
  by_agent: Record<string, ADKAgentTokens>;
}

export interface ToolParallelism {
  parallel_detected: boolean;
  overlap_pairs: number;
  tool_call_count: number;
}

export interface OTelMetrics {
  llm_call_count?: number;
  avg_llm_latency_s?: number;
  tool_call_count?: number;
  tool_parallelism?: ToolParallelism;
}

export interface ADKMetrics {
  total_wall_s: number;
  phases: ADKPhases;
  agents: ADKAgents;
  tokens: ADKTokenMetrics;
  otel?: OTelMetrics;
}

export interface AsyncTokenMetrics {
  total_input: number;
  total_output: number;
  llm_calls?: number;
  llm_total_s?: number;
  cache_read_tokens?: number;
  cache_create_tokens?: number;
}

export interface AsyncMetrics {
  total_wall_s: number;
  phases: OriginalPhases; // same shape: phase1_wall_s, phase2_wall_s, phase3_wall_s
  agents: OriginalAgents; // same shape as original
  tokens: AsyncTokenMetrics;
}

export interface BenchmarkReport {
  topic: string;
  timestamp: string;
  original?: OrchestratorMetrics;
  adk?: ADKMetrics;
  async?: AsyncMetrics;
}

/** True when a report carries at least one orchestrator's numbers.
 *
 * `GET /run/{id}` returns `benchmark: {}` for a run served from the database
 * rather than from memory, so "present" and "has data" are different questions.
 * Checking all three arms also avoids the bug this replaces, which tested only
 * `original || adk` and so declared an async-only run empty.
 */
export function hasBenchmarkData(
  report: BenchmarkReport | null | undefined
): report is BenchmarkReport {
  return !!report && !!(report.original || report.adk || report.async);
}

// ─── API / run state ────────────────────────────────────────────────────────

export interface OutputPaths {
  notes_md?: string;
  flashcards_md?: string;
  notes_pdf?: string;
  flashcards_pdf?: string;
  video?: string;
}

export interface RunState {
  run_id: string;
  topic: string;
  started_at: string;
  status: RunStatus;
  phase: RunPhase;
  progress_pct: number;
  log_lines: string[];
  outputs: OutputPaths;
  error: string | null;

  /** Absent on runs the server rebuilt from the database. */
  mode?: RunMode;
  run_dir?: string;
  /** `{}` rather than null when the server has no report for this run. */
  benchmark?: BenchmarkReport | null;

  // Set when these materials were reused from a similar earlier prompt.
  from_cache?: boolean;
  include_video?: boolean;
  cached_topic?: string | null;
}

export interface RunSummary {
  run_id: string;
  topic: string;
  status: RunStatus;
  started_at: string;
  progress_pct: number;
  phase: RunPhase;
  mode?: RunMode;
}

/** A benchmark run kept deliberately, from benchmarks/. */
export interface CuratedBenchmark {
  name: string;
  report: BenchmarkReport;
}

/** Counts behind the sidebar meters. Run figures are per-user; the prompt
 *  cache is process-wide, so its numbers are the same for everybody. */
export interface Stats {
  runs_total: number;
  runs_complete: number;
  runs_active: number;
  cache: { entries: number; hits: number };
}

export interface SSEEvent {
  log?: string | null; // present on log-line events; null for phase-only updates
  phase?: RunPhase; // current phase at time of event
  progress_pct?: number; // 0-100
  done?: boolean; // terminal sentinel — close EventSource on receipt
}

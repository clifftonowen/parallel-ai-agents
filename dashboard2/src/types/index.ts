// Shared TypeScript types for the dashboard

export type RunMode = "both" | "original" | "adk" | "async" | "all";
export type RunStatus = "running" | "complete" | "error";
export type RunPhase =
  | "starting"
  | "phase1"
  | "phase2"
  | "phase3"
  | "profiling"
  | "done"
  | "error";

// ─── Benchmark JSON shape (from benchmark_profile.py) ──────────────────────

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
  phases: OriginalPhases;   // same shape: phase1_wall_s, phase2_wall_s, phase3_wall_s
  agents: OriginalAgents;   // same shape as original
  tokens: AsyncTokenMetrics;
}

export interface BenchmarkReport {
  topic: string;
  timestamp: string;
  original?: OrchestratorMetrics;
  adk?: ADKMetrics;
  async?: AsyncMetrics;
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
  mode: RunMode;
  started_at: string;
  status: RunStatus;
  phase: RunPhase;
  progress_pct: number;
  log_lines: string[];
  benchmark: BenchmarkReport | null;
  outputs: OutputPaths;
  run_dir: string;
  error: string | null;
}

export interface RunSummary {
  run_id: string;
  topic: string;
  mode: RunMode;
  status: RunStatus;
  started_at: string;
  progress_pct: number;
  phase: RunPhase;
}

export interface SSEEvent {
  log?: string | null;       // present on log-line events; null for phase-only updates
  phase?: RunPhase;          // current phase at time of event
  progress_pct?: number;     // 0-100
  done?: boolean;            // terminal sentinel — close EventSource on receipt
}

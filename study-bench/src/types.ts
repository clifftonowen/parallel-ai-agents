// Learner-facing types. Benchmark/mode/comparison shapes are intentionally omitted —
// the study package is the only thing this app surfaces.

export interface User {
  email: string;
}

export interface AuthResponse {
  token: string;
  email: string;
}

export type RunStatus = "running" | "complete" | "error" | "cancelled";
export type RunPhase =
  | "starting"
  | "phase1"
  | "phase2"
  | "phase3"
  | "profiling"
  | "done"
  | "error";

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
  // Set when these materials were reused from a similar earlier prompt.
  from_cache?: boolean;
  cached_topic?: string | null;
}

export interface RunSummary {
  run_id: string;
  topic: string;
  status: RunStatus;
  started_at: string;
  progress_pct: number;
  phase: RunPhase;
}

export interface SSEEvent {
  log?: string | null;
  phase?: RunPhase;
  progress_pct?: number;
  done?: boolean;
}

import type { RunMode, RunState, RunSummary, SSEEvent } from "../types";

const BASE = "/api";

// ─── REST helpers ─────────────────────────────────────────────────────────

export async function startRun(
  topic: string,
  mode: RunMode
): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${BASE}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, mode }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? "Failed to start run");
  }
  return res.json();
}

export async function getRun(run_id: string): Promise<RunState> {
  const res = await fetch(`${BASE}/run/${run_id}`);
  if (!res.ok) throw new Error("Run not found");
  return res.json();
}

export async function listRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${BASE}/runs`);
  if (!res.ok) throw new Error("Failed to list runs");
  return res.json();
}

// ─── SSE streaming ────────────────────────────────────────────────────────

export function streamRun(
  run_id: string,
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError?: (err: Error) => void
): () => void {
  const es = new EventSource(`${BASE}/run/${run_id}/stream`);

  es.onmessage = (e: MessageEvent) => {
    try {
      const event: SSEEvent = JSON.parse(e.data);
      onEvent(event);
      if (event.done) {
        es.close();
        onDone();
      }
    } catch {
      // ignore malformed frames
    }
  };

  es.onerror = () => {
    es.close();
    onError?.(new Error("SSE connection error"));
    onDone();
  };

  return () => es.close();
}

// ─── File helpers ────────────────────────────────────────────────────────

export function fileUrl(run_id: string, filename: string): string {
  return `${BASE}/file/${run_id}/${encodeURIComponent(filename)}`;
}

export function downloadFile(run_id: string, filename: string): void {
  const a = document.createElement("a");
  a.href = fileUrl(run_id, filename);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export function downloadZip(run_id: string): void {
  window.open(`${BASE}/run/${run_id}/download`, "_blank");
}

export async function fetchFileText(run_id: string, filename: string): Promise<string> {
  const res = await fetch(fileUrl(run_id, filename));
  if (!res.ok) throw new Error(`Failed to fetch ${filename}`);
  return res.text();
}

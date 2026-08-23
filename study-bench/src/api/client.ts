import type { AuthResponse, RunState, RunSummary, SSEEvent, User } from "../types";

const BASE = "/api";

// This app always runs the async pipeline — the fastest, cache/tiering-optimized path.
const MODE = "async";

// ── Auth token ───────────────────────────────────────────────────────────────
// Held in memory and mirrored to localStorage by AuthContext. Threaded into every
// request so the backend can attribute runs and history to the signed-in user.
let _token: string | null = localStorage.getItem("sb_token");

export function setToken(token: string | null): void {
  _token = token;
  if (token) localStorage.setItem("sb_token", token);
  else localStorage.removeItem("sb_token");
}

export function getToken(): string | null {
  return _token;
}

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return _token ? { ...extra, Authorization: `Bearer ${_token}` } : extra;
}

// ── Runs ────────────────────────────────────────────────────────────────────

export async function startRun(
  topic: string,
  includeVideo = true,
): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${BASE}/run`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ topic, mode: MODE, include_video: includeVideo }),
  });
  if (!res.ok) {
    // A dead backend surfaces through the dev proxy as a 5xx with an HTML body,
    // so res.json() fails and statusText is "Internal Server Error" - accurate
    // but useless to a reader. Only trust a detail the API actually sent.
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail)
      .catch(() => undefined);
    throw new Error(
      detail ??
        "Couldn't reach the study server. Make sure the backend is running, then try again.",
    );
  }
  return res.json();
}

export async function getRun(run_id: string): Promise<RunState> {
  const res = await fetch(`${BASE}/run/${run_id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("That study session couldn't be found.");
  return res.json();
}

export async function listRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${BASE}/runs`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Couldn't load recent sessions.");
  return res.json();
}

// Stop an in-progress run and its generation work on the server.
export async function cancelRun(run_id: string): Promise<void> {
  const res = await fetch(`${BASE}/run/${run_id}/cancel`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Couldn't stop this session.");
}

// ── Accounts ──────────────────────────────────────────────────────────────────

async function postAuth(path: string, email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? "Something went wrong. Try again.");
  }
  return res.json();
}

export function signup(email: string, password: string): Promise<AuthResponse> {
  return postAuth("/auth/signup", email, password);
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return postAuth("/auth/login", email, password);
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, { method: "POST", headers: authHeaders() }).catch(() => {});
}

export async function me(): Promise<User | null> {
  if (!_token) return null;
  const res = await fetch(`${BASE}/auth/me`, { headers: authHeaders() });
  if (!res.ok) return null;
  return res.json();
}

// ── Live progress (SSE) ───────────────────────────────────────────────────────

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
    onError?.(new Error("Lost the connection to the study server."));
    onDone();
  };

  return () => es.close();
}

// ── Files ─────────────────────────────────────────────────────────────────────
// <video src>, download anchors and window.open() can't send an Authorization
// header, so owned-run file URLs carry the token as a query param the backend also
// accepts. fetchFileText uses the header (it's a normal fetch).

function withToken(url: string): string {
  return _token ? `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(_token)}` : url;
}

export function fileUrl(run_id: string, filename: string): string {
  return withToken(`${BASE}/file/${run_id}/${encodeURIComponent(filename)}`);
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
  window.open(withToken(`${BASE}/run/${run_id}/download`), "_blank");
}

export async function fetchFileText(run_id: string, filename: string): Promise<string> {
  const res = await fetch(`${BASE}/file/${run_id}/${encodeURIComponent(filename)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Couldn't open ${filename}.`);
  return res.text();
}

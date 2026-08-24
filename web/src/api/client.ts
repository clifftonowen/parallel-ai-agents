import type {
  AccessRequestRow, AccessState, AuthResponse, CuratedBenchmark, RunMode,
  RunState, RunSummary, SSEEvent, Stats, User,
} from "../types";
import * as demo from "./demo";
import { DEMO } from "./demo";

/**
 * Where the API lives.
 *
 * Unset means `/api`, which the dev proxy forwards after stripping the prefix.
 * Deployed, VITE_API_BASE is the backend's **origin root with no `/api`
 * suffix** — the proxy strips that prefix and the backend's routes are
 * unprefixed, so a value ending in `/api` gives a uniform 404 against a
 * completely healthy backend.
 *
 * In a demo build nothing reaches the network at all; every exported function
 * below answers from src/api/demo.ts instead.
 */
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

// Async is the default: the fastest path, and the only one with --skip-video.
// The other modes exist for the benchmark comparison; "all" runs three
// orchestrators in sequence, which is roughly 36 minutes and 3x the spend, so
// it is never the default.
const DEFAULT_MODE: RunMode = "async";

// ── Auth token ───────────────────────────────────────────────────────────────
// Held in memory and mirrored to localStorage by AuthContext. Threaded into every
// request so the backend can attribute runs and history to the signed-in user.
let _token: string | null = localStorage.getItem("sb_token");

export function setToken(token: string | null): void {
  _token = token;
  if (token) localStorage.setItem("sb_token", token);
  else localStorage.removeItem("sb_token");
  // Run grants outlive the session that issued them, so signing out has to
  // drop them too. Otherwise the next person at this browser gets working
  // media URLs for the previous person's runs.
  clearGrants();
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
  mode: RunMode = DEFAULT_MODE,
): Promise<{ run_id: string; status: string }> {
  // The composer disables Generate in a demo build, so this is unreachable
  // rather than a path a visitor can walk into. Guarded anyway: a run costs
  // real money and must never be startable by accident.
  if (DEMO) throw demo.unavailable("Starting a run");
  const res = await fetch(`${BASE}/run`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ topic, mode, include_video: includeVideo }),
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
  if (DEMO) {
    if (run_id !== demo.DEMO_RUN_ID) throw new Error("That study session couldn't be found.");
    return demo.run();
  }
  const res = await fetch(`${BASE}/run/${run_id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("That study session couldn't be found.");
  return res.json();
}

export async function listRuns(): Promise<RunSummary[]> {
  if (DEMO) return demo.runs();
  const res = await fetch(`${BASE}/runs`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Couldn't load recent sessions.");
  return res.json();
}

// Stop an in-progress run and its generation work on the server.
export async function stats(): Promise<Stats> {
  if (DEMO) return demo.stats();
  const res = await fetch(`${BASE}/stats`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load stats");
  return res.json();
}

export async function myAccessState(): Promise<AccessState> {
  if (DEMO) return demo.access();
  const res = await fetch(`${BASE}/access-request`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load access state");
  return res.json();
}

export async function requestAccess(
  name: string,
  org: string,
  message: string,
): Promise<{ status: string }> {
  if (DEMO) throw demo.unavailable("Requesting access");
  const res = await fetch(`${BASE}/access-request`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ name, org, message }),
  });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (b as { detail?: string }).detail)
      .catch(() => undefined);
    throw new Error(detail ?? "Couldn't send that request. Try again in a moment.");
  }
  return res.json();
}

/** Admin only. Returns 404 rather than 403 to anyone else, so this rejects
 *  exactly like a route that does not exist. */
export async function accessRequestQueue(
  status = "pending",
): Promise<AccessRequestRow[]> {
  // Empty rather than an error: to a non-admin this endpoint 404s, and in a
  // demo build nobody is an admin, so an empty queue is the honest answer.
  if (DEMO) return [];
  const res = await fetch(`${BASE}/access-requests?status=${status}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to load the queue");
  return res.json();
}

export async function curatedBenchmarks(): Promise<CuratedBenchmark[]> {
  // The one page whose content is identical either way: the server reads these
  // from benchmarks/, and a demo build compiles the same files in.
  if (DEMO) return demo.benchmarks();
  const res = await fetch(`${BASE}/benchmarks`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to load benchmarks");
  return res.json();
}

export async function cancelRun(run_id: string): Promise<void> {
  if (DEMO) throw demo.unavailable("Cancelling a run");
  const res = await fetch(`${BASE}/run/${run_id}/cancel`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Couldn't stop this session.");
}

// ── Accounts ──────────────────────────────────────────────────────────────────

async function postAuth(path: string, email: string, password: string): Promise<AuthResponse> {
  // The sign-in page does not render its form in a demo build. A form that
  // always fails is worse than an honest explanation.
  if (DEMO) throw demo.unavailable("Signing in");
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
  if (DEMO) return;
  await fetch(`${BASE}/auth/logout`, { method: "POST", headers: authHeaders() }).catch(() => {});
}

export async function me(): Promise<User | null> {
  // Not an error: "nobody is signed in" is a real answer, and it is the one
  // the whole demo build is built around.
  if (DEMO) return null;
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
  // /stream is authenticated and EventSource cannot set an Authorization
  // header, so something has to go in the query string. It is a run grant now,
  // not the session token. See runGrant below.
  //
  // Fetching that grant is async while this function is not, because callers
  // use it inside a useEffect and expect a cleanup function back immediately.
  // So the connection opens once the grant arrives, and the returned cleanup
  // closes whatever exists by then.
  // No run is ever in flight in a demo build — the fixture is already
  // complete — so there is nothing to stream and nothing to connect to.
  if (DEMO) {
    onDone();
    return () => {};
  }

  let es: EventSource | null = null;
  let cancelled = false;

  const attach = (source: EventSource) => {
    source.onmessage = (e: MessageEvent) => {
      try {
        const event: SSEEvent = JSON.parse(e.data);
        onEvent(event);
        if (event.done) {
          source.close();
          onDone();
        }
      } catch {
        // ignore malformed frames
      }
    };

    source.onerror = () => {
      source.close();
      onError?.(new Error("Lost the connection to the study server."));
      onDone();
    };
  };

  runGrant(run_id)
    .then((t) => {
      if (cancelled) return;
      es = new EventSource(
        `${BASE}/run/${run_id}/stream${t ? `?t=${encodeURIComponent(t)}` : ""}`,
      );
      attach(es);
    })
    .catch(() => {
      if (cancelled) return;
      onError?.(new Error("Couldn't open the live log for this run."));
      onDone();
    });

  return () => {
    cancelled = true;
    es?.close();
  };
}

// ── Run grants ────────────────────────────────────────────────────────────────
// <video src>, download anchors and window.open() cannot send an Authorization
// header, so something has to travel in the URL. It used to be the session
// token, which put full account access into browser history, Referer headers
// and every proxy log along the way. A grant reads one run's files for under
// an hour and can do nothing else. fetchFileText still uses the header: it is
// a normal fetch and never needed any of this.

type Grant = { t: string; expires: number };

const _grants = new Map<string, Grant>();
const _inflight = new Map<string, Promise<string>>();

// Refresh a little before expiry rather than at it, so a request that starts
// just inside the window does not arrive just outside it.
const GRANT_MARGIN_MS = 60_000;

/**
 * A URL credential for one run, cached until shortly before it expires.
 *
 * Concurrent callers share one request: a results page mounts a video, a
 * download button and a log stream in the same moment, and three round trips
 * for the same string would be three chances to race.
 */
export async function runGrant(run_id: string): Promise<string> {
  // Demo files are public static assets, so there is nothing to authorise and
  // no key to sign with. The empty string means "no grant needed"; fileUrl
  // treats it as absent.
  if (DEMO) return "";
  const held = _grants.get(run_id);
  if (held && held.expires - GRANT_MARGIN_MS > Date.now()) return held.t;

  const existing = _inflight.get(run_id);
  if (existing) return existing;

  const req = fetch(`${BASE}/run/${run_id}/grant`, { headers: authHeaders() })
    .then(async (res) => {
      if (!res.ok) throw new Error("Couldn't get access to this run's files.");
      const body: { t: string; expires_in: number } = await res.json();
      _grants.set(run_id, { t: body.t, expires: Date.now() + body.expires_in * 1000 });
      return body.t;
    })
    .finally(() => _inflight.delete(run_id));

  _inflight.set(run_id, req);
  return req;
}

/** Drop every cached grant. Called on sign-out, or they outlive the session. */
export function clearGrants(): void {
  _grants.clear();
  _inflight.clear();
}

// ── Files ─────────────────────────────────────────────────────────────────────

/**
 * A URL for one of a run's files.
 *
 * Synchronous, and the grant is a parameter rather than something fetched in
 * here, because this is called from JSX (`<video src={...}>`) where a promise
 * is no use. Pass what `useRunGrant` gives you. Without one the URL still
 * works for a run with no owner, which is the case on a laptop with no
 * accounts.
 */
export function fileUrl(run_id: string, filename: string, grant?: string | null): string {
  if (DEMO) return demo.fileUrl(filename);
  const url = `${BASE}/file/${run_id}/${encodeURIComponent(filename)}`;
  return grant ? `${url}?t=${encodeURIComponent(grant)}` : url;
}

function saveAs(url: string, filename?: string): void {
  const a = document.createElement("a");
  a.href = url;
  if (filename) a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export async function downloadFile(run_id: string, filename: string): Promise<void> {
  const t = await runGrant(run_id).catch(() => null);
  saveAs(fileUrl(run_id, filename, t), filename);
}

export async function downloadZip(run_id: string): Promise<void> {
  // Building the ZIP is server work. The session page offers the files
  // individually in a demo build rather than a button that cannot deliver.
  if (DEMO) throw demo.unavailable("Downloading the whole bundle");
  // An anchor click rather than window.open(): after awaiting the grant this
  // is no longer inside the user gesture, and a popup blocker eats a new
  // window. A download link survives that.
  const t = await runGrant(run_id).catch(() => null);
  saveAs(`${BASE}/run/${run_id}/download${t ? `?t=${encodeURIComponent(t)}` : ""}`);
}

export async function fetchFileText(run_id: string, filename: string): Promise<string> {
  if (DEMO) return demo.fileText(filename);
  const res = await fetch(`${BASE}/file/${run_id}/${encodeURIComponent(filename)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Couldn't open ${filename}.`);
  return res.text();
}

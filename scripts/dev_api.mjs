/**
 * dev_api.mjs
 *
 * Launches the FastAPI backend for `npm run dev`.
 *
 * This exists because `python -m uvicorn` is not reliable as an npm script: a
 * bare `python` on PATH is usually the system interpreter, which has none of
 * this project's dependencies, so the script died with ModuleNotFoundError
 * before any of our code ran.
 *
 * Resolution order, first hit wins:
 *   1. $PIPELINE_PYTHON            explicit override
 *   2. $VIRTUAL_ENV                an already-activated venv
 *   3. ../venv, ../.venv, ./venv, ./.venv   in Windows and POSIX layouts
 *   4. python3, then python        whatever is on PATH
 *
 * Deliberately no absolute paths: this file is committed and has to work on
 * someone else's machine.
 */

import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:net";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const binDir = isWindows ? "Scripts" : "bin";
const exe = isWindows ? "python.exe" : "python";

function candidates() {
  const found = [];
  if (process.env.PIPELINE_PYTHON) found.push(process.env.PIPELINE_PYTHON);
  if (process.env.VIRTUAL_ENV) {
    found.push(join(process.env.VIRTUAL_ENV, binDir, exe));
  }
  for (const venv of ["../venv", "../.venv", "venv", ".venv"]) {
    found.push(resolve(projectRoot, venv, binDir, exe));
  }
  return found;
}

const interpreter = candidates().find((p) => existsSync(p));

if (!interpreter) {
  console.error(
    [
      "",
      "Could not find a Python interpreter with this project's dependencies.",
      "",
      "Create one and install the requirements:",
      "",
      "  python -m venv .venv",
      isWindows
        ? "  .venv\\Scripts\\pip install -r requirements.txt"
        : "  .venv/bin/pip install -r requirements.txt",
      "",
      "Or point PIPELINE_PYTHON at an existing one.",
      "",
    ].join("\n"),
  );
  process.exit(1);
}

const PORT = Number(process.env.API_PORT || 8010);

// Fail loudly if the port is already taken. Another project of Cliffton's runs
// a uvicorn on 8000; if we start anyway, Vite proxies /api straight to it and
// the front-ends talk to a stranger's API with confusing errors rather than an
// obvious failure.
/** Who is listening on `port`, or null. Windows only; returns a PID string. */
function listenerPid(port) {
  if (process.platform !== "win32") return null;
  const out = spawnSync("netstat", ["-ano"], { encoding: "utf8" }).stdout ?? "";
  for (const line of out.split("\n")) {
    if (!line.includes("LISTENING")) continue;
    const local = line.trim().split(/\s+/)[1] ?? "";
    if (!local.endsWith(`:${port}`)) continue;
    const parts = line.trim().split(/\s+/);
    return parts[parts.length - 1];
  }
  return null;
}

/** The command line of a PID, or "" if it has already exited. */
function commandLine(pid) {
  if (process.platform !== "win32") return "";
  const ps = spawnSync(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      `(Get-CimInstance Win32_Process -Filter "ProcessId=${pid}").CommandLine`,
    ],
    { encoding: "utf8" },
  );
  return (ps.stdout ?? "").trim();
}

/**
 * Reclaim the port if, and only if, whatever holds it is one of ours.
 *
 * uvicorn --reload runs the real server in a child spawned through
 * multiprocessing. If the supervisor dies in a way it cannot intercept -- Task
 * Manager, Stop-Process, a terminal that went away -- that child survives
 * holding the listening socket. netstat then names an owner PID that no longer
 * exists, taskkill on it says "process not found", and the port keeps
 * answering with whatever code the stale child loaded. Every later
 * `npm run dev` then fails its preflight against a server nobody can find.
 *
 * If the recorded owner is gone, hunt the multiprocessing child naming it as
 * parent and kill that. If the owner is alive but is plainly our own
 * api_server, take the tree down. Anything else -- another project's backend,
 * a stranger's process -- is left completely alone and we fail loudly instead.
 */
function reclaimPort(port) {
  const pid = listenerPid(port);
  if (!pid) return false;

  const owner = commandLine(pid);

  if (owner === "") {
    const hunt = spawnSync(
      "powershell",
      [
        "-NoProfile",
        "-Command",
        `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*parent_pid=${pid}*' } | ForEach-Object { $_.ProcessId }`,
      ],
      { encoding: "utf8" },
    );
    const orphans = (hunt.stdout ?? "").split(/\s+/).filter(Boolean);
    if (orphans.length === 0) return false;
    console.log(
      `[dev:api] port ${port} was held by an orphaned reload child of dead PID ${pid}; clearing it`,
    );
    for (const o of orphans) {
      spawnSync("taskkill", ["/pid", o, "/T", "/F"], { stdio: "ignore" });
    }
    return true;
  }

  if (owner.includes("api_server:app") && owner.includes(`--port ${port}`)) {
    console.log(
      `[dev:api] port ${port} still held by an earlier api_server (PID ${pid}); restarting it`,
    );
    spawnSync("taskkill", ["/pid", pid, "/T", "/F"], { stdio: "ignore" });
    return true;
  }

  return false;
}

async function portFree(port) {
  return new Promise((resolve) => {
    const probe = createServer();
    probe.once("error", (err) => resolve(err.code !== "EADDRINUSE"));
    probe.once("listening", () => probe.close(() => resolve(true)));
    probe.listen(port, "127.0.0.1");
  });
}

if (!(await portFree(PORT))) {
  // One attempt to clear a leftover of our own, then re-probe.
  if (reclaimPort(PORT)) await new Promise((r) => setTimeout(r, 1500));

  if (!(await portFree(PORT))) {
    console.error(
      [
        "",
        `Port ${PORT} is already in use, so the backend did not start.`,
        "",
        "Something that is not ours is listening there - check with:",
        `  netstat -ano | findstr :${PORT}`,
        "",
        "Stop it, or run on another port with API_PORT=8011 npm run dev",
        "(the front-end proxy reads API_PORT too, so both move together).",
        "",
      ].join("\n"),
    );
    process.exit(1);
  }
}

console.log(`[dev:api] using ${interpreter}`);

// uvicorn's --reload already watches only *.py by default, so writes to
// output/ and study_bench.db during a run cannot trigger a restart.
const child = spawn(
  interpreter,
  ["-m", "uvicorn", "api_server:app", "--port", String(PORT), "--reload"],
  {
    cwd: projectRoot,
    stdio: "inherit",
    // Its own process group, so the POSIX branch of killTree() can signal the
    // whole tree rather than just the supervisor.
    detached: process.platform !== "win32",
    // So the pipeline subprocess resolves the same interpreter rather than
    // falling back to whatever `python` happens to mean.
    env: { ...process.env, PIPELINE_PYTHON: interpreter },
  },
);

child.on("exit", (code, signal) => {
  process.exit(signal ? 1 : (code ?? 0));
});

// uvicorn --reload runs the real server in a child it spawns through
// multiprocessing. Killing only the supervisor orphans that child, and on
// Windows the orphan keeps the listening socket -- the port stays busy, still
// answering with whatever code it loaded, while `netstat` names an owner PID
// that no longer exists. That is genuinely confusing to debug: the next
// `npm run dev` fails its port check, and anything that does start talks to a
// stale server.
//
// So take the whole tree down. On Windows that means taskkill /T, because
// there are no process groups; elsewhere the negative PID signals the group.
function killTree() {
  if (child.exitCode !== null || child.signalCode !== null) return;
  if (process.platform === "win32") {
    // spawnSync, not spawn: an async kill loses the race against our own
    // exit, and the orphan survives -- which is the whole bug this exists to
    // prevent.
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      shell: false,
    });
  } else {
    try {
      process.kill(-child.pid, "SIGTERM");
    } catch {
      child.kill("SIGTERM");
    }
  }
}

for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => {
    killTree();
    process.exit(0);
  });
}
process.on("exit", killTree);

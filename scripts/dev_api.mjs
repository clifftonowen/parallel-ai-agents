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

import { spawn } from "node:child_process";
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
await new Promise((done) => {
  const probe = createServer();
  probe.once("error", (err) => {
    if (err.code === "EADDRINUSE") {
      console.error(
        [
          "",
          `Port ${PORT} is already in use, so the backend did not start.`,
          "",
          "Something else is listening there - check with:",
          `  netstat -ano | findstr :${PORT}`,
          "",
          `Stop it, or run on another port with API_PORT=8001 npm run dev`,
          "(the front-ends' /api proxy targets 8010, so if you change this you",
          " must change the proxy target in each vite.config.ts too).",
          "",
        ].join("\n"),
      );
      process.exit(1);
    }
    done();
  });
  probe.once("listening", () => probe.close(done));
  probe.listen(PORT, "127.0.0.1");
});

console.log(`[dev:api] using ${interpreter}`);

// uvicorn's --reload already watches only *.py by default, so writes to
// output/ and study_bench.db during a run cannot trigger a restart.
const child = spawn(
  interpreter,
  ["-m", "uvicorn", "api_server:app", "--port", String(PORT), "--reload"],
  {
    cwd: projectRoot,
    stdio: "inherit",
    // So the pipeline subprocess resolves the same interpreter rather than
    // falling back to whatever `python` happens to mean.
    env: { ...process.env, PIPELINE_PYTHON: interpreter },
  },
);

child.on("exit", (code, signal) => {
  process.exit(signal ? 1 : (code ?? 0));
});

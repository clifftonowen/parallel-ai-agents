# parallel-ai-agents — Study Bench

A research codebase for parallelising LLM-driven content generation. The
pipeline takes a topic and produces a bundle of study artifacts — structured
notes, flashcards, a PDF, and a narrated video — by fanning a single research
stage out to several specialised agents that run concurrently.

The project is developed as part of an Undergraduate Research Opportunities
Programme (UROP) at the Singapore University of Technology and Design.

## Project scope

The repository hosts three complementary tracks:

1. **Benchmark track (Vertex AI / Gemini).** Standalone scripts that compare
   `asyncio`-based concurrency against `multiprocessing`-based parallelism for
   fan-out across three and six agents. Used to quantify true vs. concurrent
   execution and to inform the eventual Rust port.
2. **Pipeline track (Anthropic / Claude).** The working study-content pipeline
   built on the Claude API with tool use — notes, flashcards, video, PDFs.
3. **Dashboard & orchestration-variants track.** A FastAPI backend
   (`api_server.py`) that runs the pipeline on demand and streams progress,
   three interchangeable orchestrator implementations benchmarked head-to-head
   by `benchmark_profile.py`, and one React front-end. A semantic prompt cache
   (`prompt_cache.py`) and a local accounts store (`auth_db.py`) support it.

## Pipeline

1. **Notes** (sequential) — `NotesAgent` (Claude Sonnet) researches the topic
   via web/image search and writes `notes.md`, plus a `timing.json` sidecar
   used to pace the video narration.
2. **Flashcards + Video + notes PDF** (parallel) — `FlashcardAgent` builds
   Obsidian-style flashcards; `VideoAgent` builds narrated slides (HTML → PNG
   via Playwright, TTS via OpenAI `tts-1-hd`, assembled with MoviePy into
   `study_video.mp4` plus a `.pptx`); `PDFAgent` renders `notes.pdf`. The notes
   PDF only depends on Phase 1, so it runs alongside rather than waiting.
3. **Flashcards PDF** (sequential, after flashcards succeed) — `PDFAgent`
   renders `flashcards.pdf`.

Each run writes every artifact to `output/{topic_slug}_{timestamp}/`.

### Target architecture

```
Topic + difficulty tier (beginner / intermediate / advanced)
        |
        v
Gemini Deep Research        (Interactions API; background task with polling)
        |
        v
Notes agent (Claude)        (raw research -> notes.md + timing.json sidecar)
        |
        v
notes.md + timing.json
        |
   ----------------------------------------------------     parallel fan-out
   |                |                  |               |
   v                v                  v               v
Flashcard agent  HTML agent         Video agent     PDF agent
-> flashcards.md -> notes.html      -> study_       -> notes.pdf
                    + diagrams         video.mp4       (via pandoc)
   |                |                  |               |
   ----------------------------------------------------
                          |
                          v
              Orchestrator (collects + validates artifacts)
                          |
                          v
              Output bundle
```

The HTML agent and the Gemini Deep Research front-end remain the active work.

![Architecture diagram](docs/architecture-diagram.jpg)

### Three orchestrators, one interface

All three implement `__init__(anthropic_api_key, openai_api_key, output_dir)`
and `run(topic)`, so they are interchangeable for benchmarking:

- `src/agents/orchestrator.py` — `StudyOrchestrator`, the stable entry point.
  Parallelism via `concurrent.futures.ThreadPoolExecutor`.
- `src/agents/async_orchestrator.py` — `AsyncStudyOrchestrator`. Pure asyncio
  (`asyncio.gather` plus `run_in_executor`), model tiering (notes stays Sonnet,
  flashcards/video use Haiku), and Anthropic prompt caching.
- `src/agents/adk_orchestrator.py` — `ADKStudyOrchestrator`. Declarative Google
  ADK `SequentialAgent`/`ParallelAgent` graph using `AnthropicLlm` (not Gemini),
  reusing the prompt-building logic from `specialist_agent.py` via thin wrapper
  agents in `src/agents/adk_agents.py`.

## Repository layout

```
.
├── examples/                Standalone Gemini-track reference scripts
│   ├── parallel_agent.py        Three-agent fan-out (asyncio + multiprocessing)
│   ├── parallel_agent_6.py      Six-agent fan-out
│   ├── chat_session.py          Stateful vs. stateless chat reference
│   └── benchmark_test.py        asyncio-vs-multiprocessing timing demo
├── api_server.py            FastAPI dashboard backend (REST + SSE), port 8010
├── auth_db.py               SQLite-backed local accounts (study_bench.db)
├── benchmark_profile.py     Profiles the orchestrator variants
├── prompt_cache.py          Semantic (embedding-similarity) prompt cache
├── profiling_results_*.json Captured benchmark runs
├── requirements.txt
├── package.json             Root launcher only (concurrently)
├── web/                     The front-end (React + Vite + TS), port 5273
└── src/agents/
    ├── base_agent.py            AbstractStudyAgent + tool definitions
    ├── config.py                require_env() and shared configuration helpers
    ├── specialist_agent.py      NotesAgent, FlashcardAgent, VideoAgent, PDFAgent
    ├── orchestrator.py          Thread-pool pipeline driver
    ├── async_orchestrator.py    asyncio variant
    ├── adk_orchestrator.py      Google ADK variant
    ├── adk_agents.py            ADK agent definitions (AnthropicLlm models)
    └── adk_tools.py             Tools exposed to the ADK agents
```

## Prerequisites

- Python 3.11 or newer, Node 20.17+ for the front-ends.
- `ffmpeg` on `PATH` (required by `moviepy` for the video stage).
- `pandoc` plus a PDF engine (required by `PDFAgent`). The agent auto-detects
  whichever engine is installed — a LaTeX engine (`tectonic`, `xelatex`,
  `lualatex`, `pdflatex`) or an HTML engine (`wkhtmltopdf`, `weasyprint`) — and
  resolves both by absolute path, so neither needs to be on `PATH`.
- The Eisvogel LaTeX template is optional but recommended for nicer PDFs.
  Install to `%APPDATA%\pandoc\templates\eisvogel.latex` (Windows) or
  `~/.pandoc/templates/eisvogel.latex`. It is only used when the resolved
  engine is a LaTeX one; otherwise basic formatting is applied.
- A Google Cloud project with the Vertex AI API enabled (benchmark track).
- API access to Anthropic Claude and OpenAI (pipeline track).

### Installing ffmpeg and pandoc

**macOS** (Homebrew):

```
brew install ffmpeg pandoc
brew install --cask basictex      # LaTeX engine for the PDF stage
```

**Windows** (winget):

```
winget install Gyan.FFmpeg
winget install JohnMacFarlane.Pandoc
winget install MiKTeX.MiKTeX       # LaTeX engine for the PDF stage
```

`tectonic` is a lighter alternative to a full LaTeX distribution. If it is not
in your `winget` source, download the Windows binary from
https://github.com/tectonic-typesetting/tectonic/releases and place
`tectonic.exe` in `%LOCALAPPDATA%\Tectonic` — `PDFAgent` searches there.

If `ffmpeg` is missing, `VideoAgent` cannot assemble `study_video.mp4`. If
`pandoc` or a PDF engine is missing, PDF export is skipped and the rest of the
bundle is still produced.

## Setup

### 1. Install dependencies

```
pip install -r requirements.txt
playwright install
```

`playwright install` downloads the browser binaries used for HTML-to-PNG slide
rendering. `ddgs` backs the `web_search` / `image_search` tools the `NotesAgent`
calls; without it those tool calls return an install-hint string instead of
real results.

### 2. Authenticate Google Cloud (benchmark track)

The Vertex AI SDK uses Application Default Credentials, not a static API key:

```
gcloud auth application-default login
```

### 3. Configure environment variables

Copy `.env.example` to `.env` at the repository root and fill it in. All
scripts call `load_dotenv()` and resolve configuration from that file.

```
# Anthropic Claude — every orchestrator and benchmark_profile.py
ANTHROPIC_API_KEY=...

# OpenAI — text-to-speech in the video agent, embeddings for the prompt cache
OPENAI_API_KEY=...

# Google / Gemini (benchmark track)
GOOGLE_API_KEY=...
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=asia-southeast1

# Semantic prompt cache (optional)
CACHE_ENABLED=1
CACHE_SIM_THRESHOLD=0.78
CACHE_EMBED_MODEL=text-embedding-3-small
```

`.env` is git-ignored. Do not commit credentials.

## Usage

### Everything at once

```
npm install    # one-time; installs `concurrently` at the repo root only
npm run dev    # api :8010, web :5273
```

Ctrl+C stops both. This only touches the root `package.json` — the front-end
keeps its own `node_modules`, which must already be installed (`npm install`
inside `web/`).

If something else already holds 8010, `API_PORT=8011 npm run dev` moves the
backend and the Vite proxy together.

### Benchmark track (Gemini)

Each script defines a fixed prompt at the bottom of the file.

```
python examples/parallel_agent.py     # 3 agents; asyncio and multiprocessing
python examples/parallel_agent_6.py   # 6 agents; asyncio and multiprocessing
python examples/chat_session.py       # ChatSession vs. stateless generate_content
```

Each run prints per-agent PID, thread name, and elapsed time, followed by the
total wall-clock time for the batch.

### Pipeline track, no server

```
python -m src.agents.orchestrator        # StudyOrchestrator (thread pool)
python src/agents/async_orchestrator.py  # AsyncStudyOrchestrator
python src/agents/adk_orchestrator.py    # ADKStudyOrchestrator
```

Written to `output/{topic_slug}_{timestamp}/`:

```
notes.md                 structured Markdown notes
timing.json              per-section timing sidecar (drives the video)
flashcards.md            Obsidian-style spaced-repetition cards
slides/                  per-section HTML slides + PNG screenshots
audio/                   per-section TTS narration (MP3)
study_video.mp4          final narrated study video
notes.pdf, flashcards.pdf  PDF renders (only if pandoc + a PDF engine exist)
```

### Benchmark comparison CLI

```
python benchmark_profile.py --topic "your topic" [--adk-only|--original-only|--async-only] [--no-cprofile] [--otel]
```

Writes a console comparison table plus `profiling_results_<timestamp>.json`
(and `.prof` files unless `--no-cprofile`).

### Dashboard / API server

`api_server.py` accepts a topic, spawns `benchmark_profile.py` as a subprocess
to run one or more orchestrator variants, and exposes the results over REST and
server-sent events.

```
uvicorn api_server:app --reload --port 8010
```

Interactive API docs at `http://localhost:8010/docs`. Key endpoints:

| Method & path | Purpose |
| --- | --- |
| `POST /run` | Start a run. Body: `{"topic": "...", "mode": "both"}` — `mode` is one of `original`, `async`, `adk`, `both`, `all`. |
| `GET /run/{run_id}` | Poll run state (status, progress, benchmark timings). |
| `GET /run/{run_id}/stream` | Server-sent-events live log stream. |
| `POST /run/{run_id}/cancel` | Cancel a running job. |
| `GET /run/{run_id}/download` | Download a ZIP of that run's output files. |
| `GET /file/{run_id}/{filename}` | Fetch a single output file. |
| `GET /runs` | List all past runs. |
| `POST /auth/signup`, `/auth/login`, `/auth/logout`, `GET /auth/me` | Optional accounts (`auth_db.py`, `study_bench.db`). |
| `GET /health` | Liveness check. |

### Front-end

Vite + React + TypeScript. It proxies `/api` to the backend on port 8010,
**stripping the prefix** — backend routes are unprefixed (`/run`, not
`/api/run`). Remember that when deploying; see below.

```
cd web && npm run dev   # http://localhost:5273
```

One app, one port. The sidebar splits it into Overview (the front page), New
session (the composer), Library (past sessions) and Benchmark (the orchestrator
comparison). Reading is open; starting a run needs an account that has been
granted access.

It was two separate apps on 5273 and 5274 until they were merged; the old
`dashboard2/` and `study-bench/` directories are gone.

## Deploying

The two halves deploy separately, because they have nothing in common
operationally: the front-end is static files, and the backend spawns
ten-to-thirty-minute subprocesses driving ffmpeg, pandoc and headless Chromium.

### Front-end on Vercel

Import the repository and set **Root Directory** to `web`. The framework
preset, build command (`npm run build`) and output directory (`dist`) are
detected. `web/vercel.json` adds the SPA rewrite, without which a hard refresh
on `/session/abc` 404s.

Two environment variables, both build-time (`VITE_*` is inlined into the
bundle, so **never put a secret in one** and remember a change needs a
redeploy). `web/.env.example` documents them; the short version:

| | |
|---|---|
| `VITE_DEMO_MODE=1` | Build the standalone demo. No backend, no network calls: fixtures from one real finished run and the committed benchmark numbers are compiled in. This is what to ship while the backend is not hosted. |
| `VITE_API_BASE` | Where the live backend is. **Origin root, no `/api` suffix.** |

That suffix is the one trap worth repeating. The dev proxy strips `/api` and
the backend's routes are unprefixed, so `https://host/api` gives a uniform 404
against a completely healthy backend — indistinguishable from the backend being
down. Use `https://host`.

Whatever origin Vercel serves also has to appear in the backend's
`CORS_ORIGINS`, or the browser blocks every call.

```bash
# Build either variant locally before pushing — this is the whole check.
cd web
VITE_DEMO_MODE=1 npm run build && npm run preview   # standalone
npm run build && npm run preview                    # against a live backend
```

### The demo build

`VITE_DEMO_MODE=1` makes the app answer from `src/api/demo.ts` instead of the
network. The fixture is `web/public/demo/` — the notes, flashcards, PDFs and
narrated video from one real run (`binary search`, 2026-08-23), unedited — and
the benchmark numbers are imported straight from `benchmarks/`, so there is
still one copy of them in the repo.

Nothing in it is mocked up. Where a feature genuinely needs the backend —
signing in, starting a run, the ZIP download — the UI says so instead of
offering a control that throws.

### Backend

Not deployed yet. It needs a persistent volume, one replica and one worker (run
state is a process-local dict and `auth_db` holds a single connection), and
about 4GB — x264 plus Chromium OOMs at 2. `SIGNING_SECRET` becomes mandatory
there: more than one process signing run grants with different keys fails
roughly every other media request.

## Status

- **Done:** parallelisation research; instrumented true vs. concurrent
  execution; the Notes to (Flashcards, Video, notes PDF) to flashcards PDF
  pipeline on Claude; asyncio and Google ADK orchestrator variants;
  `benchmark_profile.py` head-to-head profiling; FastAPI backend with SSE
  streaming and optional accounts; semantic prompt cache; the front-end.
- **In progress:** per-task model benchmarking; HTML agent; Gemini Deep
  Research front-end; stateless vs. session-state benchmark dimension.
- **Planned:** customisable video output (linear vs. quiz checkpoints);
  Python vs. Rust benchmark for the orchestrator.

## License

Research code; no license has been declared. Contact the authors before
external use.

# Parallel AI Agents — Study Bench

A UROP research project comparing parallelization strategies for LLM-based
study-material generation. Given a topic, the pipeline generates notes,
flashcards, a narrated slide video, and PDFs — and the same pipeline is
implemented three different ways so the strategies can be benchmarked
against each other.

## Pipeline

1. **Notes** (sequential) — `NotesAgent` (Claude Sonnet) researches the topic
   via web/image search and writes `notes.md`, plus a `timing.json` used to
   pace the video narration.
2. **Flashcards + Video + Notes PDF** (parallel) — `FlashcardAgent` (Claude
   Haiku) builds Obsidian-style flashcards; `VideoAgent` builds narrated
   slides (HTML → PNG via Playwright, TTS via OpenAI `tts-1-hd`, assembled
   with MoviePy into `study_video.mp4` + a `.pptx`); `PDFAgent` renders
   `notes.pdf` via pandoc/xelatex (Eisvogel template if installed).
3. **Flashcards PDF** (sequential, after flashcards succeed) — `PDFAgent`
   renders `flashcards.pdf`.

Output lands in `output/{topic_slug}_{timestamp}/`.

### Three orchestrators, one interface

All three implement `__init__(anthropic_api_key, openai_api_key, output_dir)`
/ `run(topic)` so they're interchangeable for benchmarking:

- `src/agents/orchestrator.py` — `StudyOrchestrator`, the stable/production
  entry point. Parallelism via `concurrent.futures.ThreadPoolExecutor`.
- `src/agents/async_orchestrator.py` — `AsyncStudyOrchestrator`. Pure
  asyncio (`asyncio.gather` + `run_in_executor`), model tiering (notes stays
  Sonnet, flashcards/video use Haiku), and Anthropic prompt caching.
- `src/agents/adk_orchestrator.py` — `ADKStudyOrchestrator`. Declarative
  Google ADK `SequentialAgent`/`ParallelAgent` graph, using `AnthropicLlm`
  (not Gemini) as the model backend. Reuses the same prompt-building logic
  from `specialist_agent.py` via thin ADK wrapper agents in
  `src/agents/adk_agents.py`.

## Repo layout

```
src/agents/
  base_agent.py         AbstractStudyAgent base class, Anthropic tool-use loop, web/image search
  specialist_agent.py   NotesAgent, FlashcardAgent, VideoAgent, PDFAgent
  orchestrator.py       StudyOrchestrator (ThreadPoolExecutor)
  async_orchestrator.py AsyncStudyOrchestrator (asyncio)
  adk_tools.py          ADK FunctionTool wrappers for web/image search
  adk_agents.py         ADK LlmAgent/BaseAgent wrappers around the specialist agents
  adk_orchestrator.py   ADKStudyOrchestrator (Sequential/ParallelAgent graph)

api_server.py           FastAPI backend (port 8000) — run/poll/stream/download, auth
benchmark_profile.py    CLI: benchmarks all three orchestrators, writes profiling_results_*.json
auth_db.py              SQLite (study_bench.db): users, sessions, run history, prompt cache table
prompt_cache.py         Semantic cache (OpenAI embeddings + cosine similarity) for the async/learner path

dashboard2/             Benchmarking dashboard (React+Vite+TS), no auth, mode selector, port 5173
study-bench/            Learner-facing app (React+Vite+TS), auth required, fixed async mode, port 5174
```

## Running it

**All three at once** (backend + both frontends, one terminal, labeled output):
```
npm install    # one-time, installs `concurrently` at the repo root only
npm run dev    # api :8000, dashboard :5173, study-bench :5174
```
Ctrl+C stops all three. This only touches the root `package.json`/`node_modules`
— each frontend keeps its own `node_modules`, which must already be installed
(`npm install` inside `dashboard2/` and `study-bench/` respectively).

Or run each individually:

**Backend** (required by both frontends and by the pipeline's cache lookup):
```
uvicorn api_server:app --reload --port 8000
```

**Benchmarking dashboard** — compare original/ADK/async side by side:
```
cd dashboard2 && npm run dev   # http://localhost:5173
```

**Learner app** — end-user product, always runs the async pipeline:
```
cd study-bench && npm run dev  # http://localhost:5174
```

**Direct pipeline run, no server:**
```
python -m src.agents.orchestrator        # StudyOrchestrator
python src/agents/async_orchestrator.py  # AsyncStudyOrchestrator
python src/agents/adk_orchestrator.py    # ADKStudyOrchestrator
```

**Benchmark comparison CLI:**
```
python benchmark_profile.py --topic "your topic" [--adk-only|--original-only|--async-only] [--no-cprofile] [--otel]
```
Writes a console comparison table plus `profiling_results_<timestamp>.json`
(and `.prof` files unless `--no-cprofile`).

## Environment

Set in a `.env` file at repo root (loaded via `python-dotenv`):

- `ANTHROPIC_API_KEY` — required.
- `OPENAI_API_KEY` — required (TTS + embeddings).
- `CACHE_EMBED_MODEL` — optional, default `text-embedding-3-small`.
- `CACHE_SIM_THRESHOLD` — optional, default `0.78`.
- `CACHE_ENABLED` — optional, default on.

## Prerequisites

- `pandoc` + `xelatex` on PATH (PDF generation). Eisvogel LaTeX template
  optional but recommended — install to
  `%APPDATA%\pandoc\templates\eisvogel.latex` (Windows) or
  `~/.pandoc/templates/eisvogel.latex`.
- `playwright install` (Chromium) for HTML→PNG slide rendering.
- Node 20.17+ for the frontends (Vite 5; Vite 8 requires Node ^20.19).

# parallel-ai-agents — UROP project notes

SUTD UROP under Prof Oka. Goal: build a multi-agent study-content pipeline
that parallelises generation across heterogeneous output formats, and
benchmark concurrency vs. true multiprocessing (Python now, Rust port later).

Two collaborators:
- Cliffton: parallelisation, benchmarking, model selection, pipeline glue.
- Davin: per-agent output formats and downstream integrations.

## Repo orientation

Three tracks live side by side. `README.md` is the user-facing doc and is
kept accurate; this file is the working context.

**Benchmark track (Vertex AI / Gemini)** — standalone scripts under `examples/`:
`examples/parallel_agent.py` (3 agents), `examples/parallel_agent_6.py`
(6 agents), `examples/chat_session.py` (stateful vs. stateless chat),
`examples/benchmark_test.py`.
These compare `asyncio` against `multiprocessing.Pool` and are the reference
points for the eventual Rust comparison. Keep them as separate standalone
files — they are the benchmark targets, and they deliberately do not import
from `src/`.

**Pipeline track (Anthropic / Claude)** — `src/agents/`:
- `base_agent.py` — `AbstractStudyAgent` ABC, the Anthropic tool-use loop,
  and the `web_search` / `image_search` tool definitions (backed by `ddgs`).
- `specialist_agent.py` — `NotesAgent`, `FlashcardAgent`, `VideoAgent`,
  `PDFAgent`.
- `config.py` — `require_env()`. Use this instead of `os.environ["X"]` so a
  missing key produces a readable message rather than a bare `KeyError`.

**Three interchangeable orchestrators**, all sharing
`__init__(anthropic_api_key, openai_api_key, output_dir)` / `run(topic)`:
- `orchestrator.py` — `StudyOrchestrator`, thread pool. The stable one.
- `async_orchestrator.py` — `AsyncStudyOrchestrator`, pure asyncio, model
  tiering (notes Sonnet, flashcards/video Haiku), prompt caching.
- `adk_orchestrator.py` — `ADKStudyOrchestrator`, Google ADK
  `SequentialAgent`/`ParallelAgent` graph over `AnthropicLlm` (not Gemini),
  wrapping the same prompt logic via `adk_agents.py` / `adk_tools.py`.

**Dashboard track** — `api_server.py` (FastAPI, port 8000; shells out to
`benchmark_profile.py` rather than importing the orchestrators),
`auth_db.py` (SQLite accounts + run history), `prompt_cache.py` (semantic
cache), and two React+Vite+TS front-ends: `dashboard2/` (benchmarking, no
auth, :5173) and `study-bench/` (learner app, auth, :5174). The root
`package.json` is a launcher only — `npm run dev` starts all three.

Pipeline shape today: Phase 1 notes (sequential) → Phase 2 flashcards +
video + notes.pdf (parallel) → Phase 3 flashcards.pdf (sequential).

## Conventions

- Config comes from `.env` via `python-dotenv`. `.env.example` is the
  template. Never hardcode project IDs or keys.
- **One name for the Anthropic key: `ANTHROPIC_API_KEY`.** The old
  `CLAUDE_API_KEY` alias is gone; do not reintroduce it.
- Read required env vars through `require_env()` in `src/agents/config.py`.
- The Vertex AI track authenticates via `gcloud auth application-default
  login`, not an API key.
- Agents write into the run directory (`output/{slug}_{timestamp}/`) via
  `_save_output(..., output_dir=output_dir)`. `api_server.py` serves files
  by resolving against `run_dir`, so anything written outside it is
  unreachable from the front-ends.
- Never commit `output/` or `.env`. Generated media is what previously grew
  the history to ~185 MB.

## Current work

1. **HTML agent** — renders `notes.html` with embedded diagrams; consider
   Claude-generated HTML animations. Still the main gap in the target
   architecture.
2. **Gemini Deep Research stage** — a research step before `NotesAgent`,
   using the Interactions API as a background task with polling, feeding raw
   context into the notes agent.
3. **Topic + difficulty tier input** — the difficulty tier
   (beginner/intermediate/advanced) from the target architecture is not
   wired through yet.
4. **Session-state benchmark dimension** — stateless vs. context-passed-
   forward, as a fourth arm alongside the three orchestrators. Note the
   confound: the ADK orchestrator *already* has a real session-state bus
   (`adk_agents.py` publishes `notes_content`/`timing_json` into
   `ctx.session.state`), while the thread and async orchestrators pass
   artifacts as function arguments to stateless one-shot calls. So
   ADK-vs-thread conflates framework with state model — the clean experiment
   adds a stateful arm to `StudyOrchestrator` and holds the framework
   constant. `examples/chat_session.py` is the prior art for both arms.
5. **Per-task model benchmarking** — comparison table plus an abstract base
   class capturing each model's capabilities, strengths and weaknesses, used
   to decide which model handles which stage.
6. **Video customisation flag** — linear playback vs. quiz/checkpoint
   questions at fixed intervals.
7. **Python vs. Rust orchestrator benchmark** — decides whether the Rust
   port is worth pursuing.

---

## Roadmap history

Kept as a record of what was assigned when. Items still open are folded into
"Current work" above.

### Target architecture (Prof Oka, 2026-05-08)

```
Topic + difficulty tier (beginner / intermediate / advanced)
        |
        v
Gemini Deep Research                       (Interactions API, background task, polls)
        |
        v
Notes agent (Claude)                       (structures raw research -> MD + JSON sidecar)
        |
        v
notes.md + timing.json
        |
   ---------------------------------------------------     (parallel fan-out)
   |                |                  |              |
   v                v                  v              v
Flashcard agent  HTML agent         Video agent    PDF agent
-> flashcards.md -> notes.html      -> study_      -> notes.pdf
                    + diagrams         video.mp4      via pandoc
   |                |                  |              |
   ---------------------------------------------------
                          |
                          v
              Orchestrator -- collects + validates
                          |
                          v
              Output bundle
```

### Weeks 1-2
Parallelisation research: subprocess, `ProcessPoolExecutor`, LangGraph
subgraphs, CrewAI, Google ADK.

### Week 9
Distinguished true (multiprocessing) vs. false (asyncio / threading)
parallelisation; instrumented PID/thread tracking and timing in
`examples/parallel_agent.py` and `examples/parallel_agent_6.py`. Integrated
with the generation script. Davin handled image-as-base64 from agent output.

### Week 12

Cliffton:
- Benchmark different LLMs for different tasks; produce a comparison table.
  *(still open — see Current work 5)*
- Define an abstract base class capturing each model's capabilities,
  strengths, weaknesses; use it to decide which model handles which stage.
  *(still open)*

Davin:
- Convert `.txt` / `.pptx` outputs to `.md`
  (ref: https://github.com/bttger/markdown-flashcards).
- Investigate Notion.io API for delivering the output bundle. *(still open)*
- Pipeline shape: `notes -> slides -> video`, with `notes -> flashcards` in
  parallel. Consider https://marp.app for slide rendering.
- Use Claude to generate HTML animations for the video / HTML agent.
  *(still open — see Current work 1)*

### Week 13
- Add a customisation flag to the Video agent: linear playback vs. quiz /
  checkpoint questions at fixed intervals. *(still open — Current work 6)*
- Benchmark Python vs. Rust for the parallel orchestrator. *(still open —
  Current work 7)*

### Completed since
- Notes -> (flashcards ‖ video ‖ notes PDF) -> flashcards PDF pipeline.
- `PDFAgent` via pandoc with multi-engine detection and Eisvogel support.
- asyncio and Google ADK orchestrator variants.
- `benchmark_profile.py` head-to-head profiling.
- FastAPI backend with SSE streaming and optional accounts.
- Semantic prompt cache.
- Both front-ends (`dashboard2/`, `study-bench/`).
- Front-end input for topic (replaced the hardcoded topic in the old
  `src/main.py`, which no longer exists).

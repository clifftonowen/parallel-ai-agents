# parallel-ai-agents

A research codebase for parallelising LLM-driven content generation. The
pipeline takes a topic and difficulty tier as input and produces a bundle
of study artifacts — structured notes, flashcards, an HTML render, a PDF,
and a narrated video — by fanning a single research stage out to several
specialised agents that run concurrently.

The project is developed as part of an Undergraduate Research Opportunities
Programme (UROP) at the Singapore University of Technology and Design.

## Project scope

The repository hosts two complementary tracks:

1. **Benchmark track (Vertex AI / Gemini).** Standalone scripts that
   compare `asyncio`-based concurrency against `multiprocessing`-based
   parallelism for fan-out across three and six agents. Used to quantify
   true vs. concurrent execution and to inform the eventual Rust port.
2. **Pipeline track (Anthropic / Claude).** A working
   `Notes -> Flashcards -> Video` pipeline built on the Claude API with
   tool use. This is the basis for the broader study-content pipeline
   described under "Target architecture".

## Target architecture

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
              notes.md, flashcards.md, notes.html, notes.pdf, video.mp4
```

The current `src/main.py` driver implements the Notes -> Flashcards ->
Video subset sequentially. Conversion to the parallel orchestrator above
is the active work.

## Repository layout

```
.
├── parallel_agent.py        Three-agent Gemini fan-out (asyncio + multiprocessing)
├── parallel_agent_6.py      Six-agent Gemini fan-out
├── chat_session.py          Stateful vs. stateless Gemini chat reference
├── orchestrator.py          Claude-side orchestrator (work in progress)
├── benchmark_test.py        Benchmark harness
├── requirements.txt
└── src/
    ├── main.py              Pipeline entry point (Claude track)
    └── agents/
        ├── base_agent.py            AbstractStudyAgent + tool definitions
        └── specialist_agent.py      NotesAgent, FlashcardAgent, VideoAgent, PDFAgent
```

## Prerequisites

- Python 3.11 or newer.
- `ffmpeg` available on `PATH` (required by `moviepy`).
- `pandoc` available on `PATH` (required by `PDFAgent`).
- A Google Cloud project with the Vertex AI API enabled (benchmark track).
- API access to Anthropic Claude and OpenAI (pipeline track).

On macOS:

```
brew install ffmpeg pandoc
```

## Setup

### 1. Install Python dependencies

```
pip install -r requirements.txt
playwright install
```

The `playwright install` step downloads the browser binaries used by the
HTML rendering helpers in `specialist_agent.py`.

### 2. Authenticate Google Cloud (benchmark track)

The Vertex AI SDK uses Application Default Credentials rather than a
static API key:

```
gcloud auth application-default login
```

### 3. Configure environment variables

Create a `.env` file at the repository root. All scripts call
`load_dotenv()` and resolve configuration from this file.

```
# Anthropic Claude (pipeline track)
CLAUDE_API_KEY=...

# OpenAI (text-to-speech in the video agent)
OPENAI_API_KEY=...

# Google / Gemini (benchmark track)
GOOGLE_API_KEY=...
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=asia-southeast1
```

`.env` is git-ignored. Do not commit credentials.


## Usage

### Benchmark track

Each script defines a fixed prompt at the bottom of the file; modify it as
required for the experiment.

```
python parallel_agent.py     # 3 agents; asyncio and multiprocessing runs
python parallel_agent_6.py   # 6 agents; asyncio and multiprocessing runs
python chat_session.py       # ChatSession vs. stateless generate_content
```

Each run prints per-agent PID, thread name, and elapsed time, followed by
the total wall-clock time for the batch.

### Pipeline track

`src/main.py` uses package-relative imports
(`from agents.specialist_agent import ...`), so it must be invoked with
`src/` as the working directory:

```
cd src
python main.py
```

The driver runs Notes -> Flashcards -> Video on a hard-coded topic and
writes artifacts to `output/` at the repository root. To change the
subject, edit the `topic = "..."` line in `src/main.py`.

## Status

- **Done:** parallelisation research; instrumented true vs. concurrent
  execution; Notes / Flashcards / Video pipeline on Claude with `.env`
  driven configuration.
- **In progress:** target orchestrator architecture above; per-task model
  benchmarking; HTML agent.
- **Planned:** customisable video output (linear vs. quiz checkpoints);
  Python vs. Rust benchmark for the orchestrator.

## License

Research code; no license has been declared. Contact the authors before
external use.

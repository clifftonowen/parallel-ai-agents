# Curated benchmark results

Runs kept deliberately, as opposed to `output/` and `profiling_results_*.json`
at the repo root, which are working artifacts and git-ignored.

## `video-off-thread-vs-async.json`

The controlled orchestration comparison. Both arms ran the same topic
("gradient descent optimisation in machine learning") with `--skip-video` and
`CACHE_ENABLED=0`, back to back on 2026-08-24.

| | thread pool | asyncio |
|---|---|---|
| total wall | 111.1s | **94.5s** |
| phase 1 (notes, sequential) | 62.7s | 59.5s |
| **phase 2 (parallel fan-out)** | **39.5s** | **27.5s** |
| phase 3 (flashcards PDF) | 4.5s | 4.0s |
| input tokens | 9,496 | 12,577 |
| output tokens | 5,290 | 4,954 |
| LLM calls | 4 | 5 |

**asyncio is 1.18× faster overall, and 1.44× on phase 2** — the only phase whose
implementation actually differs between the two. Phases 1 and 3 are sequential
in both and land within a few percent, which is the sanity check that the
difference is coming from where it should.

### Why this run exists

The full-pipeline numbers say something different: across the earlier runs
asyncio was 0.96× — i.e. no better than the thread pool. That was not a null
result about concurrency, it was Amdahl's law. Video assembly is single-threaded
ffmpeg and **76–81% of wall time**, so parallelising the LLM stages could only
ever touch the remaining fifth, and the difference drowned.

Removing the video stage isolates the variable the project is actually about.

### Caveats, stated plainly

- **Single run per arm.** No repeats, so treat 1.18× as indicative, not
  measured-with-confidence. Phase 2's 1.44× is the more robust signal because
  it is the larger effect on the phase that differs.
- **The arms made a different number of LLM calls** (4 vs 5), so they were not
  doing identical work. Most likely the notes agent's inline-timing extraction
  succeeded in one and fell back to a second call in the other.
- **Not comparable to the June/July `profiling_results_*.json`.** Those predate
  moving the notes into a system block, which changed what every arm sends.
- **ADK is absent.** `--skip-video` is implemented for the thread pool and
  asyncio; the ADK orchestrator builds its pipeline as a declarative agent
  graph, so skipping a stage there is a structural change rather than a flag.
- **`cache_read_tokens` is 0, and that is expected.** Haiku 4.5 requires a
  4096-token cacheable prefix and these notes produce ~1700. See
  `src/agents/run_context.py::notes_system_block` for the measured numbers.

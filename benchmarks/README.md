# Benchmark results

Runs kept deliberately, as opposed to `output/` and the `profiling_results_*.json`
at the repo root, which are working artifacts and git-ignored.

The project asks whether parallelising a multi-agent pipeline pays. Two
experiments, and the short version is that the answer was in the wrong place
for a long time.

---

## 1. Thread pool against asyncio: no measurable difference

**`thread-vs-async-n5.json`**, five runs per arm, 2026-09-03.

Same topic each time (`gradient descent optimisation in machine learning`),
`--skip-video`, `CACHE_ENABLED=0`, and the arm order alternated between rounds
so that drift in API latency could not land on one side. Harness:
`scripts/repeat_benchmark.py`.

| | thread pool | shared executor |
|---|---|---|
| total wall | 96.3s +/- 9.6 | 93.4s +/- 8.1 |
| range | 84.3 to 108.3 | 82.8 to 105.2 |

**Overall 1.031x. Welch t = 0.51 on about 8 degrees of freedom.** The gap is
half a standard error. With five runs per arm this design could only have
resolved a difference of roughly 11 seconds, and the difference is 2.9.

### This replaces a claim that did not reproduce

`video-off-thread-vs-async.json` is the earlier version, kept for traceability
and superseded. It reported **1.18x overall and 1.44x on phase 2** from one run
per arm. Repeating it, the effect vanished, and a fresh single run early in the
process came out the other way entirely (0.92x). The run-to-run spread is about
three times the size of the effect that was being claimed.

### Two reasons that number could never have meant much

**The phase metric was not measuring a phase.** `benchmark_profile.py` computed

```python
"phase2_wall_s": round(max(fc_dur, vid_total, npdf_dur), 3)
```

which is the largest of the components' *own* self-reported durations. Pool
spin-up, submit latency and contention all fall outside that bracket, and those
are the only things the two arms differ on. It was measuring how long one Haiku
call happened to take. Both orchestrators now bracket each phase with
`time.monotonic()`; the derived figure is kept as `phase2_component_max_s` so
older reports stay readable.

**The arms are not what their names say.** `async_orchestrator.py` holds a
module-level `ThreadPoolExecutor` and runs every stage through
`loop.run_in_executor` around a blocking call. No coroutine awaits an async
HTTP client. Both arms are thread pools, and the real difference between them
is a shared six-worker executor against a fresh three-worker one per phase.

Also worth knowing before quoting any phase-2 figure: with `--skip-video` that
phase is two tasks, and one of them is `PDFAgent`, which makes no model call at
all and shells out to pandoc.

---

## 2. Video assembly: 17x, and only 2% of it is parallelism

**`assembly-sweep.json`**, three timings per configuration, 2026-09-03.

Video assembly is 75 to 81% of wall time in all seven full runs on disk, and it
was the one stage the benchmark deleted with `--skip-video` rather than
measured. Measured directly against a seven-slide deck already on disk, so no
model is called and the run costs nothing. Harness:
`scripts/bench_assembly.py`.

| configuration | wall | vs MoviePy |
|---|---|---|
| MoviePy, one encode | 489.3s +/- 43.3 | 1.00x |
| 1 ffmpeg, **still serial** | 38.7s +/- 0.9 | **12.64x** |
| 2 concurrent | 32.6s +/- 1.2 | 15.02x |
| 4 concurrent | 28.9s +/- 0.6 | 16.90x |
| 7 concurrent | 28.2s +/- 1.4 | 17.37x |

**98% of the speedup is present before any parallelism.** Replacing MoviePy
with one direct ffmpeg per slide, still entirely serial, is 12.64x on its own.
Running those encodes concurrently adds a further 1.37x and saturates by about
four workers: the marginal gain goes 1.19x, then 1.13x, then 1.03x, which is
noise.

The reason is that MoviePy decodes every frame into Python, composites in
Python and re-encodes, for a slideshow whose scenes are single static images.
ffmpeg does that natively with `-loop 1`. The bottleneck was the library, not
the lack of concurrency.

Parallelism saturates early because each ffmpeg is already multi-threaded
across the machine's 16 cores, so a fifth and sixth concurrent encoder mostly
contend with the four already running.

### A note on what "true parallelism" turned out to need

The fast path uses a **thread** pool. The encoders are separate OS processes
that do not hold the GIL, so Python's only job is to start them and wait, which
is IO waiting. `multiprocessing` would have added process spawn cost to buy
nothing. Whether parallelism is real is decided by where the work runs, not by
which Python module launched it.

### Correctness

The first version of the fast path was wrong in a way the timings could not
show. It used `-shortest`, which with an infinite `-loop 1` image input stops
only after the in-flight packet: every segment overran by about 2.9 seconds,
**and by a different amount on each run**. Identical inputs produced videos of
different lengths, and each slide would have drifted further out of step with
its narration.

It now probes the narration and passes an explicit `-t`. Verified at 417.56s
against a 417.42s narration total, identical at every pool width, and matching
the video the original run produced.

---

## Reading these together

The pipeline's parallelisable LLM stages are about a fifth of a full run.
Choosing between concurrency primitives inside that fifth is worth 3%, which is
inside the noise. The other four fifths were a single-threaded encode that was
slow for a reason that had nothing to do with concurrency at all.

Amdahl's law was the whole story, and the useful move was to go and look at the
part that dominates rather than optimise the part that was easy to reach.

## Caveats that apply to both

- Single machine, 16 logical cores, Windows. Absolute times will differ
  elsewhere; the ratios should travel better than the seconds.
- Numbers taken after 2026-08-24 are not comparable to the June and July
  `profiling_results_*.json`, which predate moving the notes into a system
  block. Do not mix them in one chart.
- **ADK is absent from experiment 1.** `--skip-video` is honoured by the thread
  pool and async arms; the ADK orchestrator builds its pipeline as a
  declarative agent graph, so skipping a stage there is a structural change
  rather than a flag.
- `cache_read_tokens` is 0, and that is expected. Haiku 4.5 needs a
  4096-token cacheable prefix and these notes produce about 1700. See
  `src/agents/run_context.py::notes_system_block`.

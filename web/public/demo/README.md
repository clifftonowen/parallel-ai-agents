# The demo fixture

The output of **one real run** of the pipeline, served as static files so the
app works with no backend behind it. `VITE_DEMO_MODE=1` makes `src/api/demo.ts`
answer from here instead of the network.

Run: **`binary search`**, 2026-08-23, async orchestrator. It is the most recent
complete run in the tree, so it reflects how the pipeline behaves now rather
than five weeks ago.

| File | What it is |
|---|---|
| `notes.md` | `NotesAgent` output, six sections, six images the `image_search` tool found |
| `flashcards.md` | `FlashcardAgent` output, in the `#flashcard` format `lib/flashcards.ts` parses |
| `notes.pdf` | `PDFAgent` via pandoc |
| `flashcards.pdf` | the same, phase 3 |
| `study_video.mp4` | `VideoAgent`: LLM-written slides, TTS narration, ffmpeg assembly |

## What was and was not changed

The markdown and both PDFs are **byte-identical** to what the run produced.
Nothing was tidied, and the rough edges are part of what this shows.

The video is **not** the run's original file, and it is worth being precise
about why.

1. **The slides were re-rendered.** Every slide the model wrote came back
   wrapped in a ` ```html ` code fence, and nothing stripped it, so the browser
   rendered the fence as body text before the doctype — visible in the corner of
   every slide, and therefore in every frame of every video the pipeline had
   ever produced. That is fixed in `run_context.strip_code_fence`, used by
   `video_agent`. The five slide `.html` files this run wrote were still on
   disk, so they were re-rendered through the fixed path and the video was
   reassembled from them and the run's own `.mp3` narration. **No model or TTS
   call was made**: same words, same voice, same slides, minus the bug.

2. **It was re-encoded for the web.** 5.04 MB → 2.44 MB (x264 CRF 32
   `-tune stillimage`, mono 48k AAC, `+faststart`). Static slides compress
   almost for free; the audio is a single narrator. Nothing was cut — same
   3:43, same content.

The images in `notes.md` still point at the sites they came from. They are
deliberately not rehosted: republishing someone else's images under this domain
would be a worse problem than an occasional broken hotlink, and a broken one
degrades to its alt text.

## What this fixture cannot show

That run has no `profiling_results.json` — it predates the profiling harness —
so the session reports no benchmark, and the Benchmark page's numbers come from
`benchmarks/video-off-thread-vs-async.json` instead. That is a different topic
and a different run. Presenting one as the other would be inventing a result,
so the session simply does not claim to have one.

## Replacing it

Copy the five files out of a completed `output/<run>/` directory, then update
`DEMO_TOPIC` and `RAN_AT` in `web/src/api/demo.ts`. `src/api/demo.test.ts`
checks the shape and will fail loudly if a file goes missing or a field is
renamed, which is the failure this fixture is most likely to hit — it would
otherwise show up as a blank tab in production and nowhere else.

"""Tests for the stdout-to-progress mapping.

This is where the progress bar comes from, and it has already shipped one bug:
the server's own launch line contains the --out-json path, which matched a
pipeline pattern and pinned the bar at 90% from the first line of every run.
The `[api]` filter that fixed it is load-bearing and has no other guard.
"""

import pytest

from run_state import RunState, infer_phase


def make_state() -> RunState:
    return RunState(run_id="r1", topic="t", mode="async")


def feed(state: RunState, *lines: str) -> RunState:
    for line in lines:
        infer_phase(state, line)
    return state


class TestServerLinesAreIgnored:
    """Lines the API server writes are not pipeline output.

    Regression test for the bug where the logged launch command contained
    `--out-json .../profiling_results.json`, matched the profiling pattern, and
    reported 90% before any work had happened.
    """

    def test_launch_line_containing_the_results_path_does_not_advance(self):
        state = make_state()
        feed(state, "[api] launching: python -u benchmark_profile.py "
                    "--out-json C:/out/r1/profiling_results.json --async-only")
        assert state.progress_pct == 0
        assert state.phase == "starting"

    @pytest.mark.parametrize(
        "line",
        [
            "[api] Warning: could not load benchmark JSON: boom",
            "  [api] indented server line",
            "[api] Phase 3 — this text would otherwise match",
            "[api] BENCHMARK RESULTS",
        ],
    )
    def test_any_api_prefixed_line_is_inert(self, line):
        state = make_state()
        feed(state, line)
        assert state.progress_pct == 0

    def test_a_pipeline_line_mentioning_api_elsewhere_still_counts(self):
        # The filter is anchored at the start, so it must not swallow real
        # output that happens to contain the string.
        state = make_state()
        feed(state, "Phase 1 — calling the api")
        assert state.phase == "phase1"


class TestPhaseProgression:
    def test_advances_through_the_pipeline(self):
        state = make_state()
        feed(state, "Async Pipeline — starting  |  topic: 'x'")
        assert (state.phase, state.progress_pct) == ("starting", 3)

        feed(state, "Phase 1 — NotesAgent")
        assert (state.phase, state.progress_pct) == ("phase1", 12)

        feed(state, "Phase 2 — FlashcardAgent")
        assert (state.phase, state.progress_pct) == ("phase2", 42)

        feed(state, "Phase 3 — PDFAgent (flashcards)")
        assert (state.phase, state.progress_pct) == ("phase3", 90)

    def test_progress_never_goes_backwards(self):
        """A late line from an earlier stage must not rewind the bar."""
        state = make_state()
        feed(state, "Phase 3 — PDFAgent")
        assert state.progress_pct == 90
        feed(state, "Phase 1 — NotesAgent")
        assert state.progress_pct == 90
        assert state.phase == "phase3"

    def test_unmatched_lines_change_nothing(self):
        state = make_state()
        feed(state, "some incidental chatter", "", "  ")
        assert state.progress_pct == 0
        assert state.phase == "starting"


class TestClosingResultsTable:
    """The summary table prints rows like "Phase 1  (Notes)" at the very end.

    Requiring the dash separator is what keeps those from reading as a phase
    change and walking the bar backwards after the run is done.
    """

    @pytest.mark.parametrize(
        "row",
        ["  Phase 1  (Notes)          62.7s",
         "  Phase 2  (Flashcards)     39.5s",
         "  Phase 3  (PDFs)            4.5s"],
    )
    def test_summary_rows_do_not_match_phase_banners(self, row):
        state = make_state()
        feed(state, row)
        assert state.progress_pct == 0, f"summary row was treated as a phase: {row!r}"

    def test_a_real_banner_with_an_em_dash_does_match(self):
        state = make_state()
        feed(state, "  Phase 2 — FlashcardAgent ‖ VideoAgent")
        assert state.phase == "phase2"

    def test_a_real_banner_with_a_hyphen_also_matches(self):
        state = make_state()
        feed(state, "Phase 2 - FlashcardAgent")
        assert state.phase == "phase2"


class TestSkipVideoRun:
    """A --skip-video run never prints the video lines and must still finish."""

    def test_reaches_done_without_any_video_output(self):
        state = make_state()
        feed(
            state,
            "Async Pipeline — starting",
            "Phase 1 — NotesAgent",
            "[Notes] Saved notes.md",
            "Phase 2 — FlashcardAgent ‖ notes.pdf  |  video skipped",
            "[Flashcards] Saved flashcards.md",
            "Phase 3 — PDFAgent",
            "Async Pipeline — complete",
        )
        assert state.phase == "done"
        assert state.progress_pct == 97

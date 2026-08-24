"""Tests for how a run is launched and which directory gets surfaced."""

import pytest

from run_manager import _pick_run_dir, build_cmd


class TestBuildCmd:
    def test_always_passes_unbuffered_and_the_run_root(self):
        cmd = build_cmd("topic", "async", "/runs/r1", "/runs/r1/out.json")
        # -u matters: without it the child block-buffers stdout when it is a
        # pipe, so progress arrives in one burst at the end.
        assert "-u" in cmd
        assert cmd[cmd.index("--run-root") + 1] == "/runs/r1"
        assert cmd[cmd.index("--out-json") + 1] == "/runs/r1/out.json"
        assert cmd[cmd.index("--topic") + 1] == "topic"

    @pytest.mark.parametrize(
        "mode, flag",
        [("async", "--async-only"), ("adk", "--adk-only"), ("original", "--original-only")],
    )
    def test_single_orchestrator_modes_pass_their_flag(self, mode, flag):
        assert flag in build_cmd("t", mode, "/r", "/r/o.json")

    @pytest.mark.parametrize("mode", ["both", "all"])
    def test_run_everything_modes_pass_no_orchestrator_flag(self, mode):
        cmd = build_cmd("t", mode, "/r", "/r/o.json")
        assert not any(a.endswith("-only") for a in cmd)

    def test_unknown_mode_passes_no_flag_rather_than_crashing(self):
        cmd = build_cmd("t", "nonsense", "/r", "/r/o.json")
        assert not any(a.endswith("-only") for a in cmd)

    def test_skip_video_only_when_video_is_off(self):
        """The flag that turns a ten-minute run into a two-minute one.

        Verified ad hoc when it shipped; pinned here because getting it
        backwards is invisible until someone waits ten minutes.
        """
        assert "--skip-video" in build_cmd("t", "async", "/r", "/r/o.json", include_video=False)
        assert "--skip-video" not in build_cmd("t", "async", "/r", "/r/o.json", include_video=True)

    def test_video_is_included_by_default(self):
        assert "--skip-video" not in build_cmd("t", "async", "/r", "/r/o.json")


class TestPickRunDir:
    """A run can produce several directories; one has to be surfaced."""

    def test_prefers_async_because_that_is_what_the_app_runs(self):
        bench = {"run_dirs": {"async": "/a", "original": "/o", "adk": "/k"}}
        assert _pick_run_dir(bench, "/fallback") == "/a"

    def test_falls_through_the_priority_order(self):
        assert _pick_run_dir({"run_dirs": {"original": "/o", "adk": "/k"}}, "/f") == "/o"
        assert _pick_run_dir({"run_dirs": {"adk": "/k"}}, "/f") == "/k"

    def test_uses_the_fallback_when_nothing_was_reported(self):
        assert _pick_run_dir({}, "/fallback") == "/fallback"
        assert _pick_run_dir({"run_dirs": {}}, "/fallback") == "/fallback"

    def test_uses_the_fallback_when_run_dirs_is_null(self):
        # The subprocess writes `"run_dirs": null` when no arm produced one.
        assert _pick_run_dir({"run_dirs": None}, "/fallback") == "/fallback"

    def test_ignores_empty_string_entries(self):
        bench = {"run_dirs": {"async": "", "original": "/o"}}
        assert _pick_run_dir(bench, "/f") == "/o"

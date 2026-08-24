"""Tests for demo-bundle discovery.

Two directory layouts coexist in output/. Older runs sit directly under
output/{slug}_{ts}/; newer ones sit under output/{run_id}/{slug}_{ts}/, because
the server now names the parent after the run id so concurrent runs cannot
collide. Missing either layout silently seeds nothing, and the failure only
shows up as an empty demo minutes before you need it.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import seed_demo  # noqa: E402


def make_bundle(parent, name, topic, *, video=False, flashcards=True):
    """A run directory the way the pipeline leaves one."""
    d = parent / name
    d.mkdir(parents=True)
    (d / "timing.json").write_text(json.dumps({"topic": topic}), encoding="utf-8")
    (d / "notes.md").write_text("# notes", encoding="utf-8")
    if flashcards:
        (d / "flashcards.md").write_text("## q #flashcard\n\na", encoding="utf-8")
    if video:
        (d / "study_video.mp4").write_bytes(b"\x00" * 64)
    return d


@pytest.fixture
def output_root(tmp_path, monkeypatch):
    root = tmp_path / "output"
    root.mkdir()
    monkeypatch.setattr(seed_demo, "OUTPUT_ROOT", str(root))
    return root


class TestLayouts:
    def test_finds_the_flat_layout(self, output_root):
        make_bundle(output_root, "binary_search_20260823_173012", "binary search")
        found = seed_demo.discover_bundles()
        assert [b["topic"] for b in found] == ["binary search"]

    def test_finds_the_nested_run_id_layout(self, output_root):
        run_id = output_root / "48893a1c-634c-4baf-8d08-b22313eafe10"
        make_bundle(run_id, "attention_20260823_235341", "attention")
        found = seed_demo.discover_bundles()
        assert [b["topic"] for b in found] == ["attention"]

    def test_finds_both_layouts_together(self, output_root):
        make_bundle(output_root, "flat_20260101_000000", "flat topic")
        make_bundle(output_root / "some-run-id", "nested_20260101_000000", "nested topic")
        topics = sorted(b["topic"] for b in seed_demo.discover_bundles())
        assert topics == ["flat topic", "nested topic"]

    def test_missing_output_root_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(seed_demo, "OUTPUT_ROOT", str(tmp_path / "does-not-exist"))
        assert seed_demo.discover_bundles() == []

    def test_skips_underscore_prefixed_directories(self, output_root):
        # output/_archive holds loose files, not a run.
        make_bundle(output_root, "_archive", "archived")
        assert seed_demo.discover_bundles() == []


class TestCompleteness:
    def test_skips_a_bundle_without_flashcards(self, output_root, capsys):
        make_bundle(output_root, "no_cards_20260101_000000", "no cards", flashcards=False)
        assert seed_demo.discover_bundles() == []
        # It says so rather than skipping silently.
        assert "incomplete" in capsys.readouterr().out

    def test_skips_a_directory_with_no_timing_json(self, output_root):
        d = output_root / "loose_20260101_000000"
        d.mkdir()
        (d / "notes.md").write_text("# notes", encoding="utf-8")
        assert seed_demo.discover_bundles() == []

    def test_skips_a_bundle_whose_timing_json_is_malformed(self, output_root):
        d = make_bundle(output_root, "bad_20260101_000000", "x")
        (d / "timing.json").write_text("{not json", encoding="utf-8")
        assert seed_demo.discover_bundles() == []

    def test_skips_a_bundle_with_an_empty_topic(self, output_root):
        d = make_bundle(output_root, "blank_20260101_000000", "x")
        (d / "timing.json").write_text(json.dumps({"topic": "   "}), encoding="utf-8")
        assert seed_demo.discover_bundles() == []


class TestOneEntryPerTopic:
    """Several runs of one topic would compete for the same query at
    near-identical similarity scores, so only the best is kept."""

    def test_deduplicates_by_topic_case_insensitively(self, output_root):
        make_bundle(output_root, "a_20260101_000000", "Binary Search")
        make_bundle(output_root, "b_20260102_000000", "binary search")
        assert len(seed_demo.discover_bundles()) == 1

    def test_prefers_the_bundle_with_a_video(self, output_root):
        make_bundle(output_root, "novideo_20260101_000000", "topic")
        make_bundle(output_root, "withvideo_20260102_000000", "topic", video=True)
        found = seed_demo.discover_bundles()
        assert len(found) == 1
        assert found[0]["has_video"] is True

    def test_prefers_the_larger_bundle_when_neither_has_video(self, output_root):
        small = make_bundle(output_root, "small_20260101_000000", "topic")
        big = make_bundle(output_root, "big_20260102_000000", "topic")
        (big / "notes.md").write_text("# notes" + "x" * 5000, encoding="utf-8")
        found = seed_demo.discover_bundles()
        assert len(found) == 1
        assert found[0]["run_dir"] == str(big)
        assert small.exists()  # the loser is not deleted, only skipped

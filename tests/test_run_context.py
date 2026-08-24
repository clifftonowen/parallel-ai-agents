"""Tests for the helpers every orchestrator shares.

These are pure string/JSON functions, which is exactly why they are worth
pinning: they sit between the model's output and the filesystem, and a silent
change in either direction desyncs a download filename from the directory it
came from.
"""

import json

import pytest

from src.agents.run_context import (
    TIMING_MARKER,
    load_timing_sections,
    make_run_dir,
    slugify_topic,
    split_notes_and_timing,
    strip_code_fence,
)


class TestSlugifyTopic:
    """The slug names run directories AND download filenames.

    There used to be four independent copies of this rule, so changing one
    silently desynced the ZIP name from the folder it came from.
    """

    @pytest.mark.parametrize(
        "topic, expected",
        [
            ("Machine Learning Basics", "machine_learning_basics"),
            ("UPPER CASE", "upper_case"),
            ("already_fine", "already_fine"),
            # Runs of non-alphanumerics collapse to a single underscore.
            ("a---b   c", "a_b_c"),
            ("What is CRISPR?", "what_is_crispr"),
            # Leading/trailing separators are trimmed, not left dangling.
            ("  spaced  ", "spaced"),
            ("!!!bang!!!", "bang"),
        ],
    )
    def test_slugs(self, topic, expected):
        assert slugify_topic(topic) == expected

    def test_truncates_to_thirty_characters(self):
        slug = slugify_topic("a" * 100)
        assert len(slug) == 30

    def test_truncation_happens_after_substitution(self):
        # A long topic of separators must not produce a 30-underscore name.
        assert slugify_topic("x" + " " * 100 + "y") == "x_y"

    def test_topic_of_only_separators_is_empty(self):
        # Documenting real behaviour rather than asserting it is desirable:
        # callers append a timestamp, so the directory is still unique.
        assert slugify_topic("???") == ""


class TestSplitNotesAndTiming:
    """The notes agent appends its timing sidecar after a marker.

    Callers treat an empty section list as "ask separately" rather than as a
    failure, so the important distinction is marker-absent versus
    marker-present-but-unparseable -- and both must yield the prose intact.
    """

    def test_marker_absent_returns_all_prose_and_no_sections(self):
        notes, sections = split_notes_and_timing("# Notes\n\nSome prose.")
        assert notes == "# Notes\n\nSome prose."
        assert sections == []

    def test_splits_prose_from_sections(self):
        raw = f'# Notes\n\nProse.\n{TIMING_MARKER}\n[{{"title": "A", "seconds": 5}}]'
        notes, sections = split_notes_and_timing(raw)
        assert notes == "# Notes\n\nProse."
        assert sections == [{"title": "A", "seconds": 5}]

    def test_strips_a_json_code_fence(self):
        # Models wrap the array in ```json even when asked not to.
        raw = f'Prose.\n{TIMING_MARKER}\n```json\n[{{"title": "A"}}]\n```'
        notes, sections = split_notes_and_timing(raw)
        assert notes == "Prose."
        assert sections == [{"title": "A"}]

    def test_malformed_json_keeps_the_prose(self):
        raw = f"Prose worth keeping.\n{TIMING_MARKER}\nnot json at all"
        notes, sections = split_notes_and_timing(raw)
        assert notes == "Prose worth keeping."
        assert sections == []

    def test_json_object_where_a_list_is_expected_is_rejected(self):
        """A dict parses fine as JSON but breaks every caller downstream.

        Callers iterate the result, so returning the dict here used to surface
        as a KeyError deep in the video stage instead of at the boundary.
        """
        raw = f'Prose.\n{TIMING_MARKER}\n{{"title": "A"}}'
        notes, sections = split_notes_and_timing(raw)
        assert notes == "Prose."
        assert sections == []

    @pytest.mark.parametrize("payload", ['"a string"', "42", "null", "true"])
    def test_other_non_list_json_is_rejected(self, payload):
        _, sections = split_notes_and_timing(f"Prose.\n{TIMING_MARKER}\n{payload}")
        assert sections == []

    def test_empty_list_is_a_valid_answer(self):
        _, sections = split_notes_and_timing(f"Prose.\n{TIMING_MARKER}\n[]")
        assert sections == []


class TestLoadTimingSections:
    """A bad sidecar should cost the video stage, not the whole run."""

    def test_reads_sections(self, tmp_path):
        p = tmp_path / "timing.json"
        p.write_text(json.dumps({"sections": [{"title": "A"}]}), encoding="utf-8")
        assert load_timing_sections(str(p)) == [{"title": "A"}]

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_timing_sections(str(tmp_path / "nope.json")) == []

    def test_malformed_json_returns_empty(self, tmp_path):
        p = tmp_path / "timing.json"
        p.write_text("{not json", encoding="utf-8")
        assert load_timing_sections(str(p)) == []

    def test_file_without_sections_key_returns_empty(self, tmp_path):
        p = tmp_path / "timing.json"
        p.write_text(json.dumps({"topic": "x"}), encoding="utf-8")
        assert load_timing_sections(str(p)) == []


class TestMakeRunDir:
    def test_creates_directory_named_slug_and_timestamp(self, tmp_path):
        from datetime import datetime

        when = datetime(2026, 8, 24, 13, 5, 9)
        run_dir = make_run_dir(str(tmp_path), "Machine Learning!", when=when)
        assert run_dir.endswith("machine_learning_20260824_130509")
        import os

        assert os.path.isdir(run_dir)

    def test_is_idempotent(self, tmp_path):
        from datetime import datetime

        when = datetime(2026, 8, 24, 13, 5, 9)
        a = make_run_dir(str(tmp_path), "topic", when=when)
        b = make_run_dir(str(tmp_path), "topic", when=when)
        assert a == b


class TestStripCodeFence:
    """Every prompt says "no markdown fences" and models add them anyway.

    Where the payload is JSON that surfaces as a parse failure, which is at
    least loud. Where it is an HTML slide it is silent: the browser renders the
    stray ```html as body text before the doctype, so it appeared in the corner
    of every slide and therefore in every frame of every video the pipeline
    produced.
    """

    def test_removes_a_fence_with_a_language_tag(self):
        assert strip_code_fence("```html\n<p>hi</p>\n```") == "<p>hi</p>"

    def test_removes_a_bare_fence(self):
        assert strip_code_fence("```\nplain\n```") == "plain"

    def test_leaves_unfenced_text_alone(self):
        assert strip_code_fence("<!DOCTYPE html>\n<p>hi</p>") == "<!DOCTYPE html>\n<p>hi</p>"

    def test_a_payload_starting_with_a_stripped_character_survives_intact(self):
        """The regression. The old code was lstrip("```json"), which reads like
        a prefix strip but is a character-set strip: it removes any leading
        backtick, j, s, o or n in any order. "null" came back as "ll". It only
        ever looked correct because every payload it saw began with [ or {.
        """
        assert strip_code_fence("```json\nnull\n```") == "null"
        assert strip_code_fence("```json\nnojson\n```") == "nojson"
        assert strip_code_fence("son of a json") == "son of a json"

    def test_an_inner_fence_is_content_not_wrapping(self):
        """Notes about code legitimately contain fences. Only a fence that
        opens the string wraps it."""
        text = "Here is an example:\n\n```python\nprint(1)\n```\n\nDone."
        assert strip_code_fence(text) == text

    def test_the_last_fence_closes_it(self):
        """A wrapped document that itself contains a fence must close on the
        outer one, not the first inner one."""
        got = strip_code_fence("```html\n<pre>```</pre>\n<p>after</p>\n```")
        assert got == "<pre>```</pre>\n<p>after</p>"

    def test_an_unclosed_fence_keeps_what_there_is(self):
        """A truncated response is still worth saving."""
        assert strip_code_fence("```html\n<p>cut off") == "<p>cut off"

    def test_a_string_that_is_only_a_fence_is_empty(self):
        assert strip_code_fence("```") == ""
        assert strip_code_fence("```html") == ""

    def test_empty_input(self):
        assert strip_code_fence("") == ""
        assert strip_code_fence("   \n  ") == ""

    def test_surrounding_whitespace_goes(self):
        assert strip_code_fence("\n\n  ```json\n[1]\n```  \n") == "[1]"

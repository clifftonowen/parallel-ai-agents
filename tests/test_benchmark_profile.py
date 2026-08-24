"""Tests for the parallelism detector.

`_check_tool_parallelism` is the function that decides whether the project's
central claim -- that the agents really do run concurrently -- is reported as
true or false. It was untested, which meant the headline finding rested on code
nobody had exercised.

It reads OpenTelemetry spans, so the fixtures below are the smallest thing that
quacks like one: a name, an attributes dict, and integer start/end times.
"""

from types import SimpleNamespace

import pytest

from benchmark_profile import _check_tool_parallelism


def span(start: int, end: int, *, tool: bool = True, name: str = "span") -> SimpleNamespace:
    """A stand-in for an OTel ReadableSpan.

    A span counts as a tool call either by its `gen_ai.operation.name`
    attribute or by "execute_tool" appearing in its name -- the detector
    accepts both, because ADK has labelled them differently across versions.
    """
    attributes = {"gen_ai.operation.name": "execute_tool"} if tool else {}
    return SimpleNamespace(name=name, attributes=attributes, start_time=start, end_time=end)


class TestSpanSelection:
    def test_ignores_spans_that_are_not_tool_calls(self):
        result = _check_tool_parallelism([span(0, 10, tool=False), span(1, 9, tool=False)])
        assert result["tool_call_count"] == 0
        assert result["parallel_detected"] is False

    def test_recognises_a_tool_span_by_its_name(self):
        spans = [
            SimpleNamespace(name="execute_tool web_search", attributes={}, start_time=0, end_time=10),
            SimpleNamespace(name="execute_tool image_search", attributes={}, start_time=5, end_time=15),
        ]
        assert _check_tool_parallelism(spans)["tool_call_count"] == 2

    def test_tolerates_attributes_being_none(self):
        # ReadableSpan.attributes can be None; `(s.attributes or {})` covers it.
        spans = [
            SimpleNamespace(name="execute_tool", attributes=None, start_time=0, end_time=10),
            SimpleNamespace(name="execute_tool", attributes=None, start_time=1, end_time=9),
        ]
        assert _check_tool_parallelism(spans)["tool_call_count"] == 2


class TestNotEnoughSpansToJudge:
    """Fewer than two tool calls cannot demonstrate parallelism either way."""

    @pytest.mark.parametrize("spans", [[], [span(0, 10)]])
    def test_reports_not_parallel_without_claiming_overlap(self, spans):
        result = _check_tool_parallelism(spans)
        assert result["parallel_detected"] is False
        assert result["tool_call_count"] == len(spans)
        # No overlap_pairs key: it has not measured anything to report.
        assert "overlap_pairs" not in result


class TestOverlapDetection:
    def test_detects_two_overlapping_calls(self):
        result = _check_tool_parallelism([span(0, 10), span(5, 15)])
        assert result["parallel_detected"] is True
        assert result["overlap_pairs"] == 1

    def test_strictly_sequential_calls_are_not_parallel(self):
        """The serial case. If this ever returns True the headline claim is
        being manufactured rather than measured."""
        result = _check_tool_parallelism([span(0, 10), span(10, 20), span(20, 30)])
        assert result["parallel_detected"] is False
        assert result["overlap_pairs"] == 0

    def test_touching_at_a_boundary_does_not_count_as_overlap(self):
        # The comparison is strict (<), so end == start is sequential.
        result = _check_tool_parallelism([span(0, 10), span(10, 20)])
        assert result["overlap_pairs"] == 0

    def test_counts_every_overlapping_pair(self):
        # Three mutually overlapping spans -> 3 pairs (AB, AC, BC).
        result = _check_tool_parallelism([span(0, 30), span(5, 25), span(10, 20)])
        assert result["overlap_pairs"] == 3
        assert result["tool_call_count"] == 3

    def test_one_overlap_among_otherwise_serial_calls_is_detected(self):
        result = _check_tool_parallelism([span(0, 10), span(20, 40), span(30, 50), span(60, 70)])
        assert result["parallel_detected"] is True
        assert result["overlap_pairs"] == 1

    def test_a_span_fully_containing_another_overlaps(self):
        result = _check_tool_parallelism([span(0, 100), span(40, 50)])
        assert result["parallel_detected"] is True

    def test_order_of_spans_does_not_matter(self):
        forward = _check_tool_parallelism([span(0, 10), span(5, 15)])
        backward = _check_tool_parallelism([span(5, 15), span(0, 10)])
        assert forward == backward

    def test_non_tool_spans_do_not_create_phantom_overlap(self):
        """Two LLM spans overlapping must not be reported as tool parallelism."""
        spans = [span(0, 10, tool=False), span(5, 15, tool=False), span(20, 30)]
        result = _check_tool_parallelism(spans)
        assert result["tool_call_count"] == 1
        assert result["parallel_detected"] is False

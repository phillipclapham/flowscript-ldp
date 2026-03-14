"""Tests for fallback chain: Mode 3 → Mode 1 → Mode 0."""

import pytest

from flowscript_ldp.fallback import FallbackChain


class TestMode3ToMode1:
    def test_semantic_frame_structure(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode1 = fallback.to_mode1()
        assert "task_type" in mode1
        assert "instruction" in mode1
        assert "input" in mode1
        assert "expected_output_format" in mode1
        assert "labels" in mode1

    def test_task_type_decision(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode1 = fallback.to_mode1()
        assert mode1["task_type"] == "decision_analysis"

    def test_instruction_is_question(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode1 = fallback.to_mode1()
        assert mode1["instruction"] == "which database?"

    def test_labels_include_types(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode1 = fallback.to_mode1()
        assert "question" in mode1["labels"]
        assert "alternative" in mode1["labels"]

    def test_degradation_metadata(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode1 = fallback.to_mode1()
        meta = mode1["metadata"]
        assert meta["degraded_from"] == 3
        assert meta["original_node_count"] == 5

    def test_input_has_nodes_and_relationships(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode1 = fallback.to_mode1()
        assert len(mode1["input"]["nodes"]) == 5
        assert len(mode1["input"]["relationships"]) > 0


class TestMode3ToMode0:
    def test_produces_readable_text(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode0 = fallback.to_mode0()
        assert isinstance(mode0, str)
        assert len(mode0) > 50
        assert "which database?" in mode0

    def test_includes_decision(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode0 = fallback.to_mode0()
        assert "Decision:" in mode0
        assert "PostgreSQL" in mode0

    def test_includes_tension(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode0 = fallback.to_mode0()
        assert "Tension" in mode0

    def test_includes_alternatives(self, decision_ir):
        fallback = FallbackChain(decision_ir)
        mode0 = fallback.to_mode0()
        assert "Option:" in mode0 or "Redis" in mode0

    def test_blockers_in_mode0(self, blocker_ir):
        fallback = FallbackChain(blocker_ir)
        mode0 = fallback.to_mode0()
        assert "Blocked:" in mode0
        assert "API keys missing" in mode0

    def test_empty_graph(self):
        from flowscript_ldp.ir import IR, GraphInvariants
        empty_ir = IR(version="1.0.0", nodes=[], relationships=[], states=[], invariants=GraphInvariants())
        fallback = FallbackChain(empty_ir)
        mode0 = fallback.to_mode0()
        assert mode0 == "(empty graph)"

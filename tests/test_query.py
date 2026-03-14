"""Tests for query engine — all 5 operations."""

import pytest

from flowscript_ldp.query import (
    AlternativesResultComparison,
    AlternativesResultSimple,
    AlternativesResultTree,
    BlockedResult,
    CausalAncestry,
    ImpactAnalysis,
    ImpactSummary,
    MinimalWhy,
    QueryEngine,
    TensionsResult,
)


class TestWhy:
    def test_causal_chain(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.why("bbb" + "0" * 61)
        assert isinstance(result, CausalAncestry)
        assert result.root_cause["content"] == "root cause"
        assert result.metadata["total_ancestors"] > 0

    def test_minimal_format(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.why("bbb" + "0" * 61, format="minimal")
        assert isinstance(result, MinimalWhy)
        assert result.root_cause == "root cause"

    def test_node_not_found(self, simple_ir):
        engine = QueryEngine(simple_ir)
        with pytest.raises(ValueError, match="Node not found"):
            engine.why("nonexistent" + "0" * 54)

    def test_root_node_is_own_root(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.why("aaa" + "0" * 61, format="minimal")
        assert isinstance(result, MinimalWhy)
        assert result.root_cause == "root cause"


class TestWhatIf:
    def test_impact_tree(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.what_if("aaa" + "0" * 61)
        assert isinstance(result, ImpactAnalysis)
        assert result.metadata["total_descendants"] > 0

    def test_summary_format(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.what_if("aaa" + "0" * 61, format="summary")
        assert isinstance(result, ImpactSummary)
        assert "root cause" in result.impact_summary

    def test_node_not_found(self, simple_ir):
        engine = QueryEngine(simple_ir)
        with pytest.raises(ValueError, match="Node not found"):
            engine.what_if("nonexistent" + "0" * 54)


class TestTensions:
    def test_tensions_by_axis(self, decision_ir):
        engine = QueryEngine(decision_ir)
        result = engine.tensions()
        assert isinstance(result, TensionsResult)
        assert result.metadata["total_tensions"] == 1
        assert "consistency vs speed" in result.metadata["unique_axes"]
        assert result.tensions_by_axis is not None

    def test_tensions_by_node(self, decision_ir):
        engine = QueryEngine(decision_ir)
        result = engine.tensions(group_by="node")
        assert result.tensions_by_node is not None

    def test_tensions_flat(self, decision_ir):
        engine = QueryEngine(decision_ir)
        result = engine.tensions(group_by="none")
        assert result.tensions is not None
        assert len(result.tensions) == 1

    def test_no_tensions(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.tensions()
        assert result.metadata["total_tensions"] == 0


class TestBlocked:
    def test_find_blockers(self, blocker_ir):
        engine = QueryEngine(blocker_ir)
        result = engine.blocked()
        assert isinstance(result, BlockedResult)
        assert result.metadata["total_blockers"] == 1
        assert result.blockers[0].blocked_state["reason"] == "waiting on vendor"

    def test_transitive_effects(self, blocker_ir):
        engine = QueryEngine(blocker_ir)
        result = engine.blocked()
        blocker = result.blockers[0]
        assert blocker.transitive_effects is not None
        assert blocker.impact_score > 0

    def test_no_blockers(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.blocked()
        assert result.metadata["total_blockers"] == 0


class TestAlternatives:
    def test_comparison_format(self, decision_ir):
        q_id = "q" * 64
        engine = QueryEngine(decision_ir)
        result = engine.alternatives(q_id)
        assert isinstance(result, AlternativesResultComparison)
        assert len(result.alternatives) == 2
        chosen = [a for a in result.alternatives if a.chosen]
        assert len(chosen) == 1
        assert chosen[0].content == "PostgreSQL"

    def test_simple_format(self, decision_ir):
        q_id = "q" * 64
        engine = QueryEngine(decision_ir)
        result = engine.alternatives(q_id, format="simple")
        assert isinstance(result, AlternativesResultSimple)
        assert result.chosen == "PostgreSQL"
        assert result.reason == "need ACID guarantees"

    def test_tree_format(self, decision_ir):
        q_id = "q" * 64
        engine = QueryEngine(decision_ir)
        result = engine.alternatives(q_id, format="tree")
        assert isinstance(result, AlternativesResultTree)
        assert len(result.alternatives) == 2

    def test_not_a_question(self, decision_ir):
        engine = QueryEngine(decision_ir)
        with pytest.raises(ValueError, match="not a question"):
            engine.alternatives("a" * 64)

    def test_with_consequences(self, decision_ir):
        q_id = "q" * 64
        engine = QueryEngine(decision_ir)
        result = engine.alternatives(q_id, include_consequences=True)
        assert isinstance(result, AlternativesResultComparison)
        pg = next(a for a in result.alternatives if a.content == "PostgreSQL")
        assert pg.consequences is not None
        assert any("consistency" in c["content"] for c in pg.consequences)

"""Tests for query engine — all 5 operations."""

import pytest

from flowscript_ldp.ir import (
    IR,
    GraphInvariants,
    Node,
    NodeType,
    Provenance,
    Relationship,
    RelationType,
)
from flowscript_ldp.query import (
    AlternativesResultComparison,
    AlternativesResultSimple,
    AlternativesResultTree,
    BlockedResult,
    CausalAncestry,
    CausalTree,
    ImpactAnalysis,
    ImpactList,
    ImpactSummary,
    MinimalWhy,
    QueryEngine,
    TensionsResult,
)


def _prov(line: int = 1) -> Provenance:
    return Provenance(source_file="test.fs", line_number=line, timestamp="2026-03-14T12:00:00Z")


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

    def test_tree_format(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.why("bbb" + "0" * 61, format="tree")
        assert isinstance(result, CausalTree)
        assert result.tree.content == "effect"
        assert len(result.tree.parents) > 0
        assert result.tree.parents[0].content == "root cause"

    def test_tree_format_multiple_parents(self):
        """Tree format shows all causal paths."""
        id_a = "a" * 64
        id_b = "b" * 64
        id_c = "c" * 64
        ir = IR(
            version="1.0.0",
            nodes=[
                Node(id=id_a, type=NodeType.STATEMENT, content="cause A", provenance=_prov(1)),
                Node(id=id_b, type=NodeType.STATEMENT, content="cause B", provenance=_prov(2)),
                Node(id=id_c, type=NodeType.STATEMENT, content="effect", provenance=_prov(3)),
            ],
            relationships=[
                Relationship(id="r1" + "0" * 62, type=RelationType.CAUSES, source=id_a, target=id_c, provenance=_prov(1)),
                Relationship(id="r2" + "0" * 62, type=RelationType.CAUSES, source=id_b, target=id_c, provenance=_prov(2)),
            ],
            states=[],
            invariants=GraphInvariants(),
        )
        engine = QueryEngine(ir)
        result = engine.why(id_c, format="tree")
        assert isinstance(result, CausalTree)
        assert len(result.tree.parents) == 2
        parent_contents = {p.content for p in result.tree.parents}
        assert parent_contents == {"cause A", "cause B"}


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

    def test_list_format(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.what_if("aaa" + "0" * 61, format="list")
        assert isinstance(result, ImpactList)
        assert len(result.consequences) > 0
        # Should be sorted by depth
        depths = [c.depth for c in result.consequences]
        assert depths == sorted(depths)

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

    def test_with_rejected_reasons(self, decision_ir):
        q_id = "q" * 64
        engine = QueryEngine(decision_ir)
        result = engine.alternatives(q_id, show_rejected_reasons=True)
        assert isinstance(result, AlternativesResultComparison)
        # Redis is rejected, but no thought nodes exist under it, so no reasons
        redis = next(a for a in result.alternatives if a.content == "Redis")
        assert not redis.chosen


class TestEdgeCases:
    """Edge cases and parameter combinations flagged by code review."""

    def test_empty_ir(self):
        empty = IR(version="1.0.0", nodes=[], relationships=[], states=[], invariants=GraphInvariants())
        engine = QueryEngine(empty)
        assert engine.tensions().metadata["total_tensions"] == 0
        assert engine.blocked().metadata["total_blockers"] == 0

    def test_why_with_max_depth(self):
        """Multi-hop chain with depth limiting."""
        ids = [f"{chr(97 + i)}" * 64 for i in range(4)]  # a*64, b*64, c*64, d*64
        ir = IR(
            version="1.0.0",
            nodes=[
                Node(id=ids[0], type=NodeType.STATEMENT, content="root", provenance=_prov(1)),
                Node(id=ids[1], type=NodeType.STATEMENT, content="mid1", provenance=_prov(2)),
                Node(id=ids[2], type=NodeType.STATEMENT, content="mid2", provenance=_prov(3)),
                Node(id=ids[3], type=NodeType.STATEMENT, content="leaf", provenance=_prov(4)),
            ],
            relationships=[
                Relationship(id=f"r{i}" + "0" * 62, type=RelationType.CAUSES, source=ids[i], target=ids[i + 1], provenance=_prov(i + 1))
                for i in range(3)
            ],
            states=[],
            invariants=GraphInvariants(),
        )
        engine = QueryEngine(ir)
        # Full depth
        result = engine.why(ids[3], format="minimal")
        assert isinstance(result, MinimalWhy)
        # Depth-limited
        limited = engine.why(ids[3], max_depth=1, format="minimal")
        assert isinstance(limited, MinimalWhy)

    def test_cyclic_graph_no_infinite_loop(self):
        """Cycle detection prevents infinite traversal."""
        id_a = "a" * 64
        id_b = "b" * 64
        ir = IR(
            version="1.0.0",
            nodes=[
                Node(id=id_a, type=NodeType.STATEMENT, content="A", provenance=_prov(1)),
                Node(id=id_b, type=NodeType.STATEMENT, content="B", provenance=_prov(2)),
            ],
            relationships=[
                Relationship(id="r1" + "0" * 62, type=RelationType.CAUSES, source=id_a, target=id_b, provenance=_prov(1)),
                Relationship(id="r2" + "0" * 62, type=RelationType.CAUSES, source=id_b, target=id_a, provenance=_prov(2), feedback=True),
            ],
            states=[],
            invariants=GraphInvariants(),
        )
        engine = QueryEngine(ir)
        # Should not hang
        result = engine.why(id_b)
        assert isinstance(result, CausalAncestry)
        result2 = engine.what_if(id_a)
        assert isinstance(result2, ImpactAnalysis)

    def test_tensions_with_scope(self, decision_ir):
        engine = QueryEngine(decision_ir)
        q_id = "q" * 64
        result = engine.tensions(scope=q_id)
        # Tensions within the question's subgraph
        assert isinstance(result, TensionsResult)

    def test_tensions_with_filter_by_axis(self, decision_ir):
        engine = QueryEngine(decision_ir)
        result = engine.tensions(filter_by_axis=["consistency vs speed"])
        assert result.metadata["total_tensions"] == 1
        result_empty = engine.tensions(filter_by_axis=["nonexistent axis"])
        assert result_empty.metadata["total_tensions"] == 0

    def test_tensions_with_context(self, decision_ir):
        engine = QueryEngine(decision_ir)
        result = engine.tensions(include_context=True)
        assert result.metadata["total_tensions"] == 1

    def test_blocked_without_transitives(self, blocker_ir):
        engine = QueryEngine(blocker_ir)
        result = engine.blocked(include_transitive_causes=False, include_transitive_effects=False)
        assert result.metadata["total_blockers"] == 1
        blocker = result.blockers[0]
        assert blocker.transitive_causes is None
        assert blocker.transitive_effects is None
        assert blocker.impact_score == 0

    def test_what_if_without_temporal(self, simple_ir):
        engine = QueryEngine(simple_ir)
        result = engine.what_if("aaa" + "0" * 61, include_temporal=False)
        assert isinstance(result, ImpactAnalysis)

    def test_no_ir_loaded_raises(self):
        engine = QueryEngine()
        with pytest.raises((ValueError, AssertionError)):
            engine.why("anything")

    def test_multiple_paths_detected(self):
        """Diamond graph: A -> C, B -> C."""
        id_a = "a" * 64
        id_b = "b" * 64
        id_c = "c" * 64
        ir = IR(
            version="1.0.0",
            nodes=[
                Node(id=id_a, type=NodeType.STATEMENT, content="path A", provenance=_prov(1)),
                Node(id=id_b, type=NodeType.STATEMENT, content="path B", provenance=_prov(2)),
                Node(id=id_c, type=NodeType.STATEMENT, content="convergence", provenance=_prov(3)),
            ],
            relationships=[
                Relationship(id="r1" + "0" * 62, type=RelationType.CAUSES, source=id_a, target=id_c, provenance=_prov(1)),
                Relationship(id="r2" + "0" * 62, type=RelationType.CAUSES, source=id_b, target=id_c, provenance=_prov(2)),
            ],
            states=[],
            invariants=GraphInvariants(),
        )
        engine = QueryEngine(ir)
        result = engine.why(id_c)
        assert isinstance(result, CausalAncestry)
        assert result.metadata["has_multiple_paths"] is True

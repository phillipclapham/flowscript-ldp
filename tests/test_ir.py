"""Tests for IR Pydantic models."""

import pytest
from pydantic import ValidationError

from flowscript_ldp.ir import (
    IR,
    Author,
    GraphInvariants,
    Node,
    NodeModifier,
    NodeType,
    Provenance,
    Relationship,
    RelationType,
    SourceSpan,
    State,
    StateFields,
    StateType,
)


class TestNodeType:
    def test_all_12_types(self):
        expected = {
            "statement", "question", "thought", "decision", "blocker",
            "insight", "action", "completion", "alternative", "exploring",
            "parking", "block",
        }
        assert {t.value for t in NodeType} == expected


class TestRelationType:
    def test_all_10_types(self):
        expected = {
            "causes", "temporal", "derives_from", "bidirectional", "tension",
            "equivalent", "different", "alternative", "alternative_worse",
            "alternative_better",
        }
        assert {t.value for t in RelationType} == expected


class TestStateType:
    def test_all_4_types(self):
        assert {t.value for t in StateType} == {"blocked", "decided", "exploring", "parking"}


class TestProvenance:
    def test_minimal(self):
        p = Provenance(source_file="test.fs", line_number=1, timestamp="2026-01-01T00:00:00Z")
        assert p.source_file == "test.fs"

    def test_with_author(self):
        p = Provenance(
            source_file="test.fs",
            line_number=1,
            timestamp="2026-01-01T00:00:00Z",
            author=Author(agent="Claude", role="ai"),
        )
        assert p.author.agent == "Claude"

    def test_invalid_line_number(self):
        with pytest.raises(ValidationError):
            Provenance(source_file="test.fs", line_number=0, timestamp="2026-01-01T00:00:00Z")


class TestNode:
    def test_basic_node(self):
        n = Node(
            id="a" * 64,
            type=NodeType.THOUGHT,
            content="some thought",
            provenance=Provenance(source_file="t.fs", line_number=1, timestamp="2026-01-01T00:00:00Z"),
        )
        assert n.type == NodeType.THOUGHT
        assert n.content == "some thought"

    def test_node_with_modifiers(self):
        n = Node(
            id="a" * 64,
            type=NodeType.STATEMENT,
            content="urgent thing",
            provenance=Provenance(source_file="t.fs", line_number=1, timestamp="2026-01-01T00:00:00Z"),
            modifiers=[NodeModifier.URGENT, NodeModifier.HIGH_CONFIDENCE],
        )
        assert NodeModifier.URGENT in n.modifiers

    def test_node_with_children(self):
        n = Node(
            id="a" * 64,
            type=NodeType.BLOCK,
            content="block",
            provenance=Provenance(source_file="t.fs", line_number=1, timestamp="2026-01-01T00:00:00Z"),
            children=["b" * 64, "c" * 64],
        )
        assert len(n.children) == 2


class TestRelationship:
    def test_tension_with_axis(self):
        r = Relationship(
            id="r" * 64,
            type=RelationType.TENSION,
            source="a" * 64,
            target="b" * 64,
            axis_label="speed vs safety",
            provenance=Provenance(source_file="t.fs", line_number=1, timestamp="2026-01-01T00:00:00Z"),
        )
        assert r.axis_label == "speed vs safety"

    def test_feedback_edge(self):
        r = Relationship(
            id="r" * 64,
            type=RelationType.CAUSES,
            source="a" * 64,
            target="b" * 64,
            provenance=Provenance(source_file="t.fs", line_number=1, timestamp="2026-01-01T00:00:00Z"),
            feedback=True,
        )
        assert r.feedback is True


class TestState:
    def test_decided_state(self):
        s = State(
            id="s" * 64,
            type=StateType.DECIDED,
            node_id="a" * 64,
            fields=StateFields(rationale="tested well", on="2026-03-14"),
            provenance=Provenance(source_file="t.fs", line_number=1, timestamp="2026-01-01T00:00:00Z"),
        )
        assert s.fields.rationale == "tested well"

    def test_blocked_state(self):
        s = State(
            id="s" * 64,
            type=StateType.BLOCKED,
            node_id="a" * 64,
            fields=StateFields(reason="waiting on API", since="2026-03-10"),
            provenance=Provenance(source_file="t.fs", line_number=1, timestamp="2026-01-01T00:00:00Z"),
        )
        assert s.fields.reason == "waiting on API"


class TestIR:
    def test_full_ir(self, simple_ir):
        assert simple_ir.version == "1.0.0"
        assert len(simple_ir.nodes) == 2
        assert len(simple_ir.relationships) == 1

    def test_serialization_roundtrip(self, simple_ir):
        data = simple_ir.model_dump(mode="json")
        restored = IR.model_validate(data)
        assert len(restored.nodes) == len(simple_ir.nodes)
        assert restored.nodes[0].content == simple_ir.nodes[0].content

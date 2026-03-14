"""Shared test fixtures."""

import pytest

from flowscript_ldp.ir import (
    IR,
    GraphInvariants,
    Node,
    NodeType,
    Provenance,
    Relationship,
    RelationType,
    State,
    StateFields,
    StateType,
)


def _prov(line: int = 1) -> Provenance:
    return Provenance(
        source_file="test.fs",
        line_number=line,
        timestamp="2026-03-14T12:00:00Z",
    )


@pytest.fixture
def simple_ir() -> IR:
    """Minimal IR with 2 nodes and 1 causal relationship."""
    return IR(
        version="1.0.0",
        nodes=[
            Node(
                id="aaa" + "0" * 61,
                type=NodeType.THOUGHT,
                content="root cause",
                provenance=_prov(1),
            ),
            Node(
                id="bbb" + "0" * 61,
                type=NodeType.STATEMENT,
                content="effect",
                provenance=_prov(2),
            ),
        ],
        relationships=[
            Relationship(
                id="rel" + "0" * 61,
                type=RelationType.CAUSES,
                source="aaa" + "0" * 61,
                target="bbb" + "0" * 61,
                provenance=_prov(2),
            ),
        ],
        states=[],
        invariants=GraphInvariants(),
    )


@pytest.fixture
def decision_ir() -> IR:
    """IR with a question, alternatives, and a decision."""
    q_id = "q" * 64
    alt1_id = "a" * 64
    alt2_id = "b" * 64
    stmt1_id = "s" * 64
    stmt2_id = "t" * 64

    return IR(
        version="1.0.0",
        nodes=[
            Node(id=q_id, type=NodeType.QUESTION, content="which database?", provenance=_prov(1)),
            Node(id=alt1_id, type=NodeType.ALTERNATIVE, content="PostgreSQL", provenance=_prov(2)),
            Node(id=alt2_id, type=NodeType.ALTERNATIVE, content="Redis", provenance=_prov(3)),
            Node(id=stmt1_id, type=NodeType.STATEMENT, content="strong consistency", provenance=_prov(4)),
            Node(id=stmt2_id, type=NodeType.STATEMENT, content="fast reads", provenance=_prov(5)),
        ],
        relationships=[
            Relationship(id="r1" + "0" * 62, type=RelationType.ALTERNATIVE, source=q_id, target=alt1_id, provenance=_prov(2)),
            Relationship(id="r2" + "0" * 62, type=RelationType.ALTERNATIVE, source=q_id, target=alt2_id, provenance=_prov(3)),
            Relationship(id="r3" + "0" * 62, type=RelationType.CAUSES, source=alt1_id, target=stmt1_id, provenance=_prov(4)),
            Relationship(id="r4" + "0" * 62, type=RelationType.CAUSES, source=alt2_id, target=stmt2_id, provenance=_prov(5)),
            Relationship(
                id="r5" + "0" * 62,
                type=RelationType.TENSION,
                source=stmt1_id,
                target=stmt2_id,
                axis_label="consistency vs speed",
                provenance=_prov(6),
            ),
        ],
        states=[
            State(
                id="st" + "0" * 62,
                type=StateType.DECIDED,
                node_id=alt1_id,
                fields=StateFields(rationale="need ACID guarantees", on="2026-03-14"),
                provenance=_prov(7),
            ),
        ],
        invariants=GraphInvariants(),
    )


@pytest.fixture
def blocker_ir() -> IR:
    """IR with blocked nodes."""
    n1_id = "n1" + "0" * 62
    n2_id = "n2" + "0" * 62
    n3_id = "n3" + "0" * 62

    return IR(
        version="1.0.0",
        nodes=[
            Node(id=n1_id, type=NodeType.BLOCKER, content="API keys missing", provenance=_prov(1)),
            Node(id=n2_id, type=NodeType.ACTION, content="deploy service", provenance=_prov(2)),
            Node(id=n3_id, type=NodeType.STATEMENT, content="users can access", provenance=_prov(3)),
        ],
        relationships=[
            Relationship(id="rb1" + "0" * 61, type=RelationType.CAUSES, source=n1_id, target=n2_id, provenance=_prov(2)),
            Relationship(id="rb2" + "0" * 61, type=RelationType.CAUSES, source=n2_id, target=n3_id, provenance=_prov(3)),
        ],
        states=[
            State(
                id="sb" + "0" * 62,
                type=StateType.BLOCKED,
                node_id=n1_id,
                fields=StateFields(reason="waiting on vendor", since="2026-03-10T00:00:00Z"),
                provenance=_prov(1),
            ),
        ],
        invariants=GraphInvariants(),
    )

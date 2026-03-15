"""
Cross-project compatibility tests: FlowScript <-> flowscript-ldp.

These tests verify that changes to the FlowScript parser/compiler don't break
the Python SDK's ability to consume IR output. They protect three contracts:

1. **Golden fixture round-trip**: The FlowScript CLI produces IR that the
   Python IR models (Pydantic) can parse without errors, and the structural
   properties (node types, relationship types, counts) match the reference
   JSON fixtures checked into the FlowScript repo.

2. **Enum coverage**: Every NodeType, RelationType, StateType, and NodeModifier
   value that appears in the golden fixtures is represented in the Python enums.
   If FlowScript adds a new type, this catches it before it causes a runtime
   crash in production.

3. **Query engine resilience**: The Python QueryEngine can load and query every
   golden fixture without crashing. We can't compare against JS query results
   directly, but we verify all 5 query operations produce well-typed results.

Run these tests:
    pytest tests/test_cross_project_compat.py -v

ParserBridge tests (round-trip via CLI) require the FlowScript CLI to be
available. They are skipped automatically in CI or environments without Node.js
and the FlowScript repo. Schema/enum/query tests run against the golden JSON
files directly and always work.

Prerequisites for full test suite:
    - Node.js installed
    - FlowScript repo at ~/Documents/flowscript/ with built CLI
    - flowscript-ldp installed in dev mode (pip install -e .)
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from flowscript_ldp.ir import (
    IR,
    Node,
    NodeModifier,
    NodeType,
    Relationship,
    RelationType,
    State,
    StateType,
)
from flowscript_ldp.parser_bridge import ParserBridge
from flowscript_ldp.query import (
    AlternativesResult,
    BlockedResult,
    CausalAncestry,
    CausalTree,
    ImpactAnalysis,
    MinimalWhy,
    QueryEngine,
    TensionsResult,
)

# =============================================================================
# Constants and helpers
# =============================================================================

FLOWSCRIPT_EXAMPLES = Path("~/Documents/flowscript/examples/").expanduser()
FLOWSCRIPT_CLI = Path("~/Documents/flowscript/dist/cli.js").expanduser()

# Golden fixture names (stem only, no extension)
GOLDEN_FIXTURES = ["decision", "debug", "research", "design"]


def _cli_available() -> bool:
    """Check if the FlowScript CLI is available and functional."""
    if not FLOWSCRIPT_CLI.exists():
        return False
    if shutil.which("node") is None:
        return False
    try:
        result = subprocess.run(
            ["node", str(FLOWSCRIPT_CLI), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


CLI_AVAILABLE = _cli_available()
SKIP_CLI = pytest.mark.skipif(
    not CLI_AVAILABLE,
    reason="FlowScript CLI not available (need Node.js + built FlowScript repo)",
)


def discover_golden_pairs() -> list[tuple[str, Path, Path]]:
    """Discover all .fs/.json pairs in the FlowScript examples directory.

    Returns list of (name, fs_path, json_path) tuples.
    """
    pairs = []
    if not FLOWSCRIPT_EXAMPLES.exists():
        return pairs
    for name in GOLDEN_FIXTURES:
        fs_path = FLOWSCRIPT_EXAMPLES / f"{name}.fs"
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if fs_path.exists() and json_path.exists():
            pairs.append((name, fs_path, json_path))
    return pairs


def load_golden_json(name: str) -> dict[str, Any]:
    """Load a golden JSON fixture by name."""
    json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
    with open(json_path) as f:
        return json.load(f)


def load_golden_ir(name: str) -> IR:
    """Load a golden JSON fixture as a validated IR model."""
    return ParserBridge.load_ir_json(FLOWSCRIPT_EXAMPLES / f"{name}.json")


GOLDEN_PAIRS = discover_golden_pairs()
GOLDEN_NAMES = [name for name, _, _ in GOLDEN_PAIRS]


# =============================================================================
# 1. Golden fixture round-trip tests (ParserBridge CLI)
# =============================================================================


@SKIP_CLI
class TestGoldenFixtureRoundTrip:
    """Parse each golden .fs file via ParserBridge, compare against reference JSON.

    These tests verify structural equivalence: same node types, relationship
    types, node count, relationship count. NOT exact ID comparison, because
    content hashing may differ between parser versions or runs with different
    timestamps.

    Note: The CLI compact output (-c flag) does not emit 'block' container
    nodes, while the golden JSON files do include them. Comparisons filter
    out block nodes to match CLI behavior.
    """

    @pytest.fixture(scope="class")
    def bridge(self) -> ParserBridge:
        return ParserBridge(cli_path=FLOWSCRIPT_CLI)

    @pytest.mark.parametrize(
        "name,fs_path,json_path",
        GOLDEN_PAIRS,
        ids=[name for name, _, _ in GOLDEN_PAIRS],
    )
    def test_parse_produces_valid_ir(
        self, bridge: ParserBridge, name: str, fs_path: Path, json_path: Path
    ):
        """CLI parse of .fs file produces a valid IR that Pydantic accepts."""
        ir = bridge.parse_file(fs_path)
        assert isinstance(ir, IR), f"{name}.fs: parse_file did not return IR"
        assert ir.version == "1.0.0", f"{name}.fs: unexpected IR version {ir.version}"

    @pytest.mark.parametrize(
        "name,fs_path,json_path",
        GOLDEN_PAIRS,
        ids=[name for name, _, _ in GOLDEN_PAIRS],
    )
    def test_node_count_matches(
        self, bridge: ParserBridge, name: str, fs_path: Path, json_path: Path
    ):
        """CLI-parsed IR has the same number of nodes as the reference JSON.

        Block nodes are excluded from the reference count because CLI compact
        mode (-c) does not emit them.
        """
        parsed_ir = bridge.parse_file(fs_path)
        reference = load_golden_json(name)
        ref_non_block = [n for n in reference["nodes"] if n["type"] != "block"]
        assert len(parsed_ir.nodes) == len(ref_non_block), (
            f"{name}: CLI produced {len(parsed_ir.nodes)} nodes, "
            f"reference has {len(ref_non_block)} non-block nodes"
        )

    @pytest.mark.parametrize(
        "name,fs_path,json_path",
        GOLDEN_PAIRS,
        ids=[name for name, _, _ in GOLDEN_PAIRS],
    )
    def test_relationship_count_matches(
        self, bridge: ParserBridge, name: str, fs_path: Path, json_path: Path
    ):
        """CLI-parsed IR has the same number of relationships as reference."""
        parsed_ir = bridge.parse_file(fs_path)
        reference = load_golden_json(name)
        assert len(parsed_ir.relationships) == len(reference["relationships"]), (
            f"{name}: CLI produced {len(parsed_ir.relationships)} relationships, "
            f"reference has {len(reference['relationships'])}"
        )

    @pytest.mark.parametrize(
        "name,fs_path,json_path",
        GOLDEN_PAIRS,
        ids=[name for name, _, _ in GOLDEN_PAIRS],
    )
    def test_state_count_matches(
        self, bridge: ParserBridge, name: str, fs_path: Path, json_path: Path
    ):
        """CLI-parsed IR has the same number of states as reference."""
        parsed_ir = bridge.parse_file(fs_path)
        reference = load_golden_json(name)
        assert len(parsed_ir.states) == len(reference["states"]), (
            f"{name}: CLI produced {len(parsed_ir.states)} states, "
            f"reference has {len(reference['states'])}"
        )

    @pytest.mark.parametrize(
        "name,fs_path,json_path",
        GOLDEN_PAIRS,
        ids=[name for name, _, _ in GOLDEN_PAIRS],
    )
    def test_node_types_match(
        self, bridge: ParserBridge, name: str, fs_path: Path, json_path: Path
    ):
        """CLI-parsed IR has the same set of node types as reference.

        Block nodes are excluded from reference because CLI compact mode
        does not emit them.
        """
        parsed_ir = bridge.parse_file(fs_path)
        reference = load_golden_json(name)
        parsed_types = sorted({n.type.value for n in parsed_ir.nodes})
        ref_types = sorted(
            {n["type"] for n in reference["nodes"] if n["type"] != "block"}
        )
        assert parsed_types == ref_types, (
            f"{name}: node type mismatch.\n"
            f"  CLI produced: {parsed_types}\n"
            f"  Reference has: {ref_types}"
        )

    @pytest.mark.parametrize(
        "name,fs_path,json_path",
        GOLDEN_PAIRS,
        ids=[name for name, _, _ in GOLDEN_PAIRS],
    )
    def test_relationship_types_match(
        self, bridge: ParserBridge, name: str, fs_path: Path, json_path: Path
    ):
        """CLI-parsed IR has the same set of relationship types as reference."""
        parsed_ir = bridge.parse_file(fs_path)
        reference = load_golden_json(name)
        parsed_types = sorted({r.type.value for r in parsed_ir.relationships})
        ref_types = sorted({r["type"] for r in reference["relationships"]})
        assert parsed_types == ref_types, (
            f"{name}: relationship type mismatch.\n"
            f"  CLI produced: {parsed_types}\n"
            f"  Reference has: {ref_types}"
        )

    @pytest.mark.parametrize(
        "name,fs_path,json_path",
        GOLDEN_PAIRS,
        ids=[name for name, _, _ in GOLDEN_PAIRS],
    )
    def test_node_contents_match(
        self, bridge: ParserBridge, name: str, fs_path: Path, json_path: Path
    ):
        """CLI-parsed IR has the same set of node content strings as reference.

        Content strings are the semantic payload. IDs may differ (hash-based),
        but the actual content must be identical across parsers. Block nodes
        are excluded from reference (CLI compact mode omits them).
        """
        parsed_ir = bridge.parse_file(fs_path)
        reference = load_golden_json(name)
        parsed_contents = sorted(n.content for n in parsed_ir.nodes)
        ref_contents = sorted(
            n["content"]
            for n in reference["nodes"]
            if n["type"] != "block"
        )
        assert parsed_contents == ref_contents, (
            f"{name}: node content mismatch.\n"
            f"  Only in CLI: {sorted(set(parsed_contents) - set(ref_contents))}\n"
            f"  Only in ref: {sorted(set(ref_contents) - set(parsed_contents))}"
        )


# =============================================================================
# 2. IR schema conformance tests (golden JSON -> Python models)
# =============================================================================


@pytest.mark.skipif(
    not FLOWSCRIPT_EXAMPLES.exists(),
    reason=f"FlowScript examples not found at {FLOWSCRIPT_EXAMPLES}",
)
class TestIRSchemaConformance:
    """Validate that every golden JSON fixture loads cleanly through Pydantic models.

    This catches schema drift: if the JS parser starts producing fields the
    Python models don't expect, or changes field shapes, these tests fail.
    """

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_model_validate_succeeds(self, name: str):
        """Golden JSON validates through IR.model_validate() without errors."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        assert isinstance(ir, IR)
        assert ir.version == "1.0.0"

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_all_nodes_have_valid_type(self, name: str):
        """Every node type in the golden fixture is a valid NodeType enum value."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        for node in ir.nodes:
            assert isinstance(node.type, NodeType), (
                f"{name}: node '{node.content}' has type '{node.type}' "
                f"which is not a valid NodeType"
            )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_all_relationships_have_valid_type(self, name: str):
        """Every relationship type is a valid RelationType enum value."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        for rel in ir.relationships:
            assert isinstance(rel.type, RelationType), (
                f"{name}: relationship '{rel.id[:12]}...' has type '{rel.type}' "
                f"which is not a valid RelationType"
            )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_all_states_have_valid_type(self, name: str):
        """Every state type is a valid StateType enum value."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        for state in ir.states:
            assert isinstance(state.type, StateType), (
                f"{name}: state '{state.id[:12]}...' has type '{state.type}' "
                f"which is not a valid StateType"
            )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_all_modifiers_are_valid(self, name: str):
        """Every node modifier is a valid NodeModifier enum value."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        for node in ir.nodes:
            if node.modifiers:
                for mod in node.modifiers:
                    assert isinstance(mod, NodeModifier), (
                        f"{name}: node '{node.content}' has modifier '{mod}' "
                        f"which is not a valid NodeModifier. "
                        f"Known modifiers: {[m.value for m in NodeModifier]}"
                    )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_node_ids_are_valid_hashes(self, name: str):
        """All node IDs are 64-char lowercase hex strings (SHA-256)."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        import re

        hash_pattern = re.compile(r"^[a-f0-9]{64}$")
        for node in ir.nodes:
            assert hash_pattern.match(node.id), (
                f"{name}: node '{node.content}' has invalid ID '{node.id}' "
                f"(expected 64-char lowercase hex)"
            )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_relationship_references_valid_nodes(self, name: str):
        """All relationship source/target IDs reference existing nodes."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        node_ids = {n.id for n in ir.nodes}
        for rel in ir.relationships:
            assert rel.source in node_ids, (
                f"{name}: relationship '{rel.id[:12]}...' references "
                f"non-existent source node '{rel.source[:12]}...'"
            )
            assert rel.target in node_ids, (
                f"{name}: relationship '{rel.id[:12]}...' references "
                f"non-existent target node '{rel.target[:12]}...'"
            )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_state_references_valid_nodes(self, name: str):
        """All state node_id fields reference existing nodes."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        node_ids = {n.id for n in ir.nodes}
        for state in ir.states:
            assert state.node_id in node_ids, (
                f"{name}: state '{state.id[:12]}...' references "
                f"non-existent node '{state.node_id[:12]}...'"
            )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_tension_relationships_have_axis_labels(self, name: str):
        """Tension relationships should have axis_label set."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        for rel in ir.relationships:
            if rel.type == RelationType.TENSION:
                assert rel.axis_label is not None and rel.axis_label != "", (
                    f"{name}: tension relationship '{rel.id[:12]}...' "
                    f"is missing axis_label"
                )


# =============================================================================
# 3. Query engine parity tests
# =============================================================================


@pytest.mark.skipif(
    not FLOWSCRIPT_EXAMPLES.exists(),
    reason=f"FlowScript examples not found at {FLOWSCRIPT_EXAMPLES}",
)
class TestQueryEngineParity:
    """Run all 5 query operations on every golden fixture.

    We can't compare against JS query results, but we verify:
    - No crashes on real-world IR data
    - Return types are correct
    - Results are internally consistent (counts match, etc.)
    """

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_tensions_query(self, name: str):
        """tensions() runs without error and returns TensionsResult."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        result = engine.tensions()
        assert isinstance(result, TensionsResult), (
            f"{name}: tensions() returned {type(result).__name__}, "
            f"expected TensionsResult"
        )
        assert "total_tensions" in result.metadata
        # Verify count consistency
        total = result.metadata["total_tensions"]
        if result.tensions_by_axis is not None:
            axis_count = sum(len(v) for v in result.tensions_by_axis.values())
            assert axis_count == total, (
                f"{name}: tensions metadata says {total} but "
                f"tensions_by_axis contains {axis_count}"
            )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_tensions_group_by_node(self, name: str):
        """tensions(group_by='node') runs without error."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        result = engine.tensions(group_by="node")
        assert isinstance(result, TensionsResult)

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_tensions_flat(self, name: str):
        """tensions(group_by='flat') runs without error."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        result = engine.tensions(group_by="flat")
        assert isinstance(result, TensionsResult)

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_blocked_query(self, name: str):
        """blocked() runs without error and returns BlockedResult."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        result = engine.blocked()
        assert isinstance(result, BlockedResult), (
            f"{name}: blocked() returned {type(result).__name__}, "
            f"expected BlockedResult"
        )
        assert result.metadata["total_blockers"] == len(result.blockers), (
            f"{name}: blocked metadata says {result.metadata['total_blockers']} "
            f"blockers but list has {len(result.blockers)}"
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_blocked_matches_state_count(self, name: str):
        """blocked() finds the same number of blockers as 'blocked' states in IR."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        result = engine.blocked()
        blocked_states = [s for s in ir.states if s.type == StateType.BLOCKED]
        assert len(result.blockers) == len(blocked_states), (
            f"{name}: blocked() found {len(result.blockers)} blockers but "
            f"IR has {len(blocked_states)} blocked states"
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_why_query_on_each_node(self, name: str):
        """why() runs without error on every non-root node."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        errors = []
        for node in ir.nodes:
            try:
                result = engine.why(node.id)
                assert isinstance(result, CausalAncestry), (
                    f"why({node.content!r}) returned {type(result).__name__}"
                )
            except Exception as e:
                errors.append(f"why({node.content!r}): {e}")
        assert not errors, (
            f"{name}: why() failed on {len(errors)} node(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_why_tree_format(self, name: str):
        """why(format='tree') runs without error on every node."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        errors = []
        for node in ir.nodes:
            try:
                result = engine.why(node.id, format="tree")
                assert isinstance(result, CausalTree)
            except Exception as e:
                errors.append(f"why({node.content!r}, format='tree'): {e}")
        assert not errors, (
            f"{name}: why(format='tree') failed on {len(errors)} node(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_why_minimal_format(self, name: str):
        """why(format='minimal') runs without error on every node."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        errors = []
        for node in ir.nodes:
            try:
                result = engine.why(node.id, format="minimal")
                assert isinstance(result, MinimalWhy)
            except Exception as e:
                errors.append(f"why({node.content!r}, format='minimal'): {e}")
        assert not errors, (
            f"{name}: why(format='minimal') failed on {len(errors)} node(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_what_if_query_on_each_node(self, name: str):
        """what_if() runs without error on every node."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        errors = []
        for node in ir.nodes:
            try:
                result = engine.what_if(node.id)
                assert isinstance(result, ImpactAnalysis), (
                    f"what_if({node.content!r}) returned {type(result).__name__}"
                )
            except Exception as e:
                errors.append(f"what_if({node.content!r}): {e}")
        assert not errors, (
            f"{name}: what_if() failed on {len(errors)} node(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_alternatives_on_question_nodes(self, name: str):
        """alternatives() runs on every question node without error,
        including questions where no alternative has a decided state.
        For fixtures without questions, verifies non-question nodes
        are correctly rejected."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        question_nodes = [n for n in ir.nodes if n.type == NodeType.QUESTION]
        if not question_nodes:
            # No questions — verify alternatives() rejects non-question nodes
            non_question = next(n for n in ir.nodes if n.content)
            with pytest.raises(ValueError, match="not a question"):
                engine.alternatives(non_question.id)
            return
        errors = []
        for node in question_nodes:
            try:
                result = engine.alternatives(node.id)
                assert isinstance(result, AlternativesResult.__args__), (
                    f"alternatives({node.content!r}) returned "
                    f"{type(result).__name__}"
                )
            except Exception as e:
                errors.append(f"alternatives({node.content!r}): {e}")
        assert not errors, (
            f"{name}: alternatives() failed on {len(errors)} question(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_alternatives_simple_format(self, name: str):
        """alternatives(format='simple') runs on every question node.
        For fixtures without questions, verifies ValueError on non-question."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        question_nodes = [n for n in ir.nodes if n.type == NodeType.QUESTION]
        if not question_nodes:
            non_question = next(n for n in ir.nodes if n.content)
            with pytest.raises(ValueError, match="not a question"):
                engine.alternatives(non_question.id, format="simple")
            return
        for node in question_nodes:
            result = engine.alternatives(node.id, format="simple")
            assert result.format == "simple"

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_alternatives_tree_format(self, name: str):
        """alternatives(format='tree') runs on every question node.
        For fixtures without questions, verifies ValueError on non-question."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        engine = QueryEngine(ir)
        question_nodes = [n for n in ir.nodes if n.type == NodeType.QUESTION]
        if not question_nodes:
            non_question = next(n for n in ir.nodes if n.content)
            with pytest.raises(ValueError, match="not a question"):
                engine.alternatives(non_question.id, format="tree")
            return
        for node in question_nodes:
            result = engine.alternatives(node.id, format="tree")
            assert result.format == "tree"


# =============================================================================
# 4. Enum coverage tests
# =============================================================================


@pytest.mark.skipif(
    not FLOWSCRIPT_EXAMPLES.exists(),
    reason=f"FlowScript examples not found at {FLOWSCRIPT_EXAMPLES}",
)
class TestEnumCoverage:
    """Verify that every type value in golden fixtures is covered by Python enums.

    These tests work at the raw JSON level (before Pydantic validation) to
    catch the exact error: an unknown string value that would cause a
    ValidationError at parse time.
    """

    def _collect_all_values(
        self, key: str, collection: str
    ) -> list[tuple[str, str]]:
        """Collect all unique values of a field across all golden fixtures.

        Returns list of (fixture_name, value) pairs.
        """
        results = []
        for name in GOLDEN_FIXTURES:
            json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
            if not json_path.exists():
                continue
            data = load_golden_json(name)
            for item in data.get(collection, []):
                value = item.get(key)
                if value is not None:
                    results.append((name, value))
        return results

    def test_all_node_types_covered(self):
        """Every node type string in golden fixtures maps to a NodeType enum."""
        known_values = {e.value for e in NodeType}
        pairs = self._collect_all_values("type", "nodes")
        unknown = []
        for fixture_name, value in pairs:
            if value not in known_values:
                unknown.append((fixture_name, value))
        # Deduplicate for reporting
        unique_unknown = sorted(set(unknown))
        assert not unique_unknown, (
            f"Unknown NodeType values found in golden fixtures "
            f"(Python enum needs updating):\n"
            + "\n".join(
                f"  - '{val}' in {fix}.json" for fix, val in unique_unknown
            )
            + f"\n\nKnown NodeType values: {sorted(known_values)}"
        )

    def test_all_relationship_types_covered(self):
        """Every relationship type string maps to a RelationType enum."""
        known_values = {e.value for e in RelationType}
        pairs = self._collect_all_values("type", "relationships")
        unknown = sorted(
            set(
                (fix, val) for fix, val in pairs if val not in known_values
            )
        )
        assert not unknown, (
            f"Unknown RelationType values found in golden fixtures "
            f"(Python enum needs updating):\n"
            + "\n".join(
                f"  - '{val}' in {fix}.json" for fix, val in unknown
            )
            + f"\n\nKnown RelationType values: {sorted(known_values)}"
        )

    def test_all_state_types_covered(self):
        """Every state type string maps to a StateType enum."""
        known_values = {e.value for e in StateType}
        pairs = self._collect_all_values("type", "states")
        unknown = sorted(
            set(
                (fix, val) for fix, val in pairs if val not in known_values
            )
        )
        assert not unknown, (
            f"Unknown StateType values found in golden fixtures "
            f"(Python enum needs updating):\n"
            + "\n".join(
                f"  - '{val}' in {fix}.json" for fix, val in unknown
            )
            + f"\n\nKnown StateType values: {sorted(known_values)}"
        )

    def test_all_modifier_values_covered(self):
        """Every modifier string in golden fixtures maps to a NodeModifier enum."""
        known_values = {e.value for e in NodeModifier}
        unknown = []
        for name in GOLDEN_FIXTURES:
            json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
            if not json_path.exists():
                continue
            data = load_golden_json(name)
            for node in data.get("nodes", []):
                for mod in node.get("modifiers", []) or []:
                    if mod not in known_values:
                        unknown.append((name, mod, node.get("content", "")))
        unique_unknown = sorted(set((f, m) for f, m, _ in unknown))
        assert not unique_unknown, (
            f"Unknown NodeModifier values found in golden fixtures "
            f"(Python enum needs updating):\n"
            + "\n".join(
                f"  - '{mod}' in {fix}.json" for fix, mod in unique_unknown
            )
            + f"\n\nKnown NodeModifier values: {sorted(known_values)}"
        )

    def test_enum_completeness_report(self):
        """Report which enum values appear vs which are defined (informational).

        This test always passes but prints coverage info for debugging.
        """
        seen_node_types: set[str] = set()
        seen_rel_types: set[str] = set()
        seen_state_types: set[str] = set()
        seen_modifiers: set[str] = set()

        for name in GOLDEN_FIXTURES:
            json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
            if not json_path.exists():
                continue
            data = load_golden_json(name)
            for node in data.get("nodes", []):
                seen_node_types.add(node["type"])
                for mod in node.get("modifiers", []) or []:
                    seen_modifiers.add(mod)
            for rel in data.get("relationships", []):
                seen_rel_types.add(rel["type"])
            for state in data.get("states", []):
                seen_state_types.add(state["type"])

        all_node_types = {e.value for e in NodeType}
        all_rel_types = {e.value for e in RelationType}
        all_state_types = {e.value for e in StateType}
        all_modifiers = {e.value for e in NodeModifier}

        # These are informational — types defined in Python but not exercised
        # by golden fixtures. Not a failure, but worth knowing.
        untested_nodes = all_node_types - seen_node_types
        untested_rels = all_rel_types - seen_rel_types
        untested_states = all_state_types - seen_state_types
        untested_mods = all_modifiers - seen_modifiers

        # This always passes; it's just a coverage report
        assert True, (
            f"Enum coverage:\n"
            f"  NodeType: {len(seen_node_types)}/{len(all_node_types)} "
            f"(untested: {untested_nodes or 'none'})\n"
            f"  RelationType: {len(seen_rel_types)}/{len(all_rel_types)} "
            f"(untested: {untested_rels or 'none'})\n"
            f"  StateType: {len(seen_state_types)}/{len(all_state_types)} "
            f"(untested: {untested_states or 'none'})\n"
            f"  NodeModifier: {len(seen_modifiers)}/{len(all_modifiers)} "
            f"(untested: {untested_mods or 'none'})"
        )


# =============================================================================
# 5. Structural invariant tests
# =============================================================================


@pytest.mark.skipif(
    not FLOWSCRIPT_EXAMPLES.exists(),
    reason=f"FlowScript examples not found at {FLOWSCRIPT_EXAMPLES}",
)
class TestStructuralInvariants:
    """Verify structural properties that the IR schema guarantees."""

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_version_is_1_0_0(self, name: str):
        """All golden fixtures use IR version 1.0.0."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        assert ir.version == "1.0.0", (
            f"{name}: unexpected version '{ir.version}' (expected '1.0.0')"
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_invariants_all_true(self, name: str):
        """Golden fixture invariants are all true (well-formed graphs)."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        assert ir.invariants.causal_acyclic, f"{name}: causal_acyclic is False"
        assert ir.invariants.all_nodes_reachable, (
            f"{name}: all_nodes_reachable is False"
        )
        assert ir.invariants.tension_axes_labeled, (
            f"{name}: tension_axes_labeled is False"
        )
        assert ir.invariants.state_fields_present, (
            f"{name}: state_fields_present is False"
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_no_orphan_relationships(self, name: str):
        """No relationship references a node ID that doesn't exist."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        node_ids = {n.id for n in ir.nodes}
        orphans = []
        for rel in ir.relationships:
            if rel.source not in node_ids:
                orphans.append(
                    f"rel {rel.id[:12]}... source {rel.source[:12]}... not found"
                )
            if rel.target not in node_ids:
                orphans.append(
                    f"rel {rel.id[:12]}... target {rel.target[:12]}... not found"
                )
        assert not orphans, (
            f"{name}: orphan relationship references:\n"
            + "\n".join(f"  - {o}" for o in orphans)
        )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_blocked_states_have_required_fields(self, name: str):
        """Blocked states have reason and since fields."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        for state in ir.states:
            if state.type == StateType.BLOCKED:
                assert state.fields is not None, (
                    f"{name}: blocked state {state.id[:12]}... has no fields"
                )
                assert state.fields.reason, (
                    f"{name}: blocked state {state.id[:12]}... missing 'reason'"
                )
                assert state.fields.since, (
                    f"{name}: blocked state {state.id[:12]}... missing 'since'"
                )

    @pytest.mark.parametrize("name", GOLDEN_FIXTURES)
    def test_decided_states_have_required_fields(self, name: str):
        """Decided states have rationale and on fields."""
        json_path = FLOWSCRIPT_EXAMPLES / f"{name}.json"
        if not json_path.exists():
            pytest.skip(f"{name}.json not found")
        ir = load_golden_ir(name)
        for state in ir.states:
            if state.type == StateType.DECIDED:
                assert state.fields is not None, (
                    f"{name}: decided state {state.id[:12]}... has no fields"
                )
                assert state.fields.rationale, (
                    f"{name}: decided state {state.id[:12]}... missing 'rationale'"
                )
                assert state.fields.on, (
                    f"{name}: decided state {state.id[:12]}... missing 'on'"
                )

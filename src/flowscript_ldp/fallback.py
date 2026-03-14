"""
Fallback Chain: Mode 3 → Mode 1 → Mode 0 conversion.

Implements LDP's automatic degradation protocol. When a higher mode fails
or the receiver doesn't support it, content gracefully degrades to simpler
representations while preserving as much semantic structure as possible.
"""

from __future__ import annotations

from typing import Any, Optional

from .ir import IR, Node, NodeType, RelationType
from .parser_bridge import ParserBridge


class FallbackChain:
    """LDP fallback chain: Mode 3 ↔ Mode 1 ↔ Mode 0."""

    def __init__(self, ir: IR):
        self._ir = ir
        self._node_map: dict[str, Node] = {n.id: n for n in ir.nodes}

    @property
    def ir(self) -> IR:
        return self._ir

    # =========================================================================
    # Mode 3 → Mode 1: Semantic Frame extraction
    # =========================================================================

    def to_mode1(self) -> dict[str, Any]:
        """Convert Mode 3 (semantic graph) to Mode 1 (semantic frame).

        Extracts structured fields from IR:
        - task_type: inferred from dominant node types
        - instruction: primary question or statement content
        - input: graph summary as structured data
        - expected_output_format: based on graph structure
        - labels: node types present
        """
        # Determine task type from node distribution
        type_counts: dict[str, int] = {}
        for node in self._ir.nodes:
            t = node.type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        task_type = self._infer_task_type(type_counts)

        # Extract primary instruction (first question or top-level statement)
        instruction = self._extract_instruction()

        # Build structured input from relationships
        input_data = self._build_structured_input()

        # Determine output format based on graph
        output_format = self._infer_output_format(type_counts)

        return {
            "task_type": task_type,
            "instruction": instruction,
            "input": input_data,
            "expected_output_format": output_format,
            "labels": sorted(type_counts.keys()),
            "metadata": {
                "degraded_from": 3,
                "original_node_count": len(self._ir.nodes),
                "original_relationship_count": len(self._ir.relationships),
                "information_preserved": "structure_and_types",
            },
        }

    def _infer_task_type(self, type_counts: dict[str, int]) -> str:
        """Infer semantic frame task_type from node type distribution."""
        if type_counts.get("question", 0) > 0 and type_counts.get("alternative", 0) > 0:
            return "decision_analysis"
        if type_counts.get("blocker", 0) > 0:
            return "blocker_resolution"
        if type_counts.get("question", 0) > 0:
            return "analysis"
        if type_counts.get("action", 0) > 0:
            return "planning"
        if type_counts.get("thought", 0) > type_counts.get("statement", 0):
            return "reasoning"
        return "synthesis"

    def _extract_instruction(self) -> str:
        """Extract primary instruction from graph."""
        # First question node
        for node in self._ir.nodes:
            if node.type == NodeType.QUESTION:
                return node.content

        # First top-level node (no incoming relationships)
        target_ids = {r.target for r in self._ir.relationships}
        for node in self._ir.nodes:
            if node.id not in target_ids:
                return node.content

        # Fallback: first node
        if self._ir.nodes:
            return self._ir.nodes[0].content
        return ""

    def _build_structured_input(self) -> dict[str, Any]:
        """Build structured representation of graph relationships."""
        result: dict[str, Any] = {"nodes": [], "relationships": []}

        for node in self._ir.nodes:
            result["nodes"].append(
                {"type": node.type.value, "content": node.content}
            )

        for rel in self._ir.relationships:
            entry: dict[str, str] = {
                "type": rel.type.value,
                "from": self._node_content(rel.source),
                "to": self._node_content(rel.target),
            }
            if rel.axis_label:
                entry["axis"] = rel.axis_label
            result["relationships"].append(entry)

        return result

    def _node_content(self, node_id: str) -> str:
        """Get node content by ID."""
        node = self._node_map.get(node_id)
        return node.content if node else f"[unknown:{node_id[:8]}]"

    def _infer_output_format(self, type_counts: dict[str, int]) -> str:
        """Infer expected output format from graph structure."""
        if type_counts.get("alternative", 0) > 0:
            return "decision+justification"
        if type_counts.get("blocker", 0) > 0:
            return "resolution+steps"
        if type_counts.get("action", 0) > 0:
            return "action_plan"
        return "analysis+reasoning"

    # =========================================================================
    # Mode 3 → Mode 0: Natural language rendering
    # =========================================================================

    def to_mode0(self) -> str:
        """Convert Mode 3 (semantic graph) to Mode 0 (natural language text).

        Renders the IR graph as readable prose, reconstructing a narrative
        from the structured relationships.
        """
        sections: list[str] = []

        # Questions
        questions = [n for n in self._ir.nodes if n.type == NodeType.QUESTION]
        for q in questions:
            sections.append(f"Question: {q.content}")
            # Find alternatives for this question
            alt_rels = [
                r
                for r in self._ir.relationships
                if r.source == q.id and r.type == RelationType.ALTERNATIVE
            ]
            for rel in alt_rels:
                alt_node = self._find_node(rel.target)
                if alt_node:
                    sections.append(f"  Option: {alt_node.content}")
                    # Children of this alternative
                    for child_id in alt_node.children or []:
                        child = self._find_node(child_id)
                        if child:
                            sections.append(f"    - {child.content}")

        # Decisions
        decided_states = [s for s in self._ir.states if s.type.value == "decided"]
        for state in decided_states:
            node = self._find_node(state.node_id)
            if node:
                rationale = state.fields.rationale if state.fields else "no rationale given"
                sections.append(f"Decision: {node.content} (because: {rationale})")

        # Blockers
        blocked_states = [s for s in self._ir.states if s.type.value == "blocked"]
        for state in blocked_states:
            node = self._find_node(state.node_id)
            if node:
                reason = state.fields.reason if state.fields else "unknown"
                sections.append(f"Blocked: {node.content} (reason: {reason})")

        # Tensions
        tension_rels = [
            r for r in self._ir.relationships if r.type == RelationType.TENSION
        ]
        if tension_rels:
            sections.append("Tensions:")
            for rel in tension_rels:
                src = self._find_node(rel.source)
                tgt = self._find_node(rel.target)
                if src and tgt:
                    axis = rel.axis_label or "unlabeled"
                    sections.append(
                        f"  {src.content} vs {tgt.content} ({axis})"
                    )

        # Thoughts and insights
        thoughts = [n for n in self._ir.nodes if n.type == NodeType.THOUGHT]
        if thoughts:
            sections.append("Key thoughts:")
            for t in thoughts:
                sections.append(f"  - {t.content}")

        insights = [n for n in self._ir.nodes if n.type == NodeType.INSIGHT]
        if insights:
            sections.append("Insights:")
            for i in insights:
                sections.append(f"  - {i.content}")

        # Causal chains (simplified)
        causal_rels = [
            r for r in self._ir.relationships if r.type == RelationType.CAUSES
        ]
        if causal_rels:
            sections.append("Causal relationships:")
            for rel in causal_rels:
                src = self._find_node(rel.source)
                tgt = self._find_node(rel.target)
                if src and tgt:
                    sections.append(f"  {src.content} → {tgt.content}")

        # Remaining statements not covered above
        covered_ids = set()
        for q in questions:
            covered_ids.add(q.id)
        for s in self._ir.states:
            covered_ids.add(s.node_id)
        for t in thoughts:
            covered_ids.add(t.id)
        for i in insights:
            covered_ids.add(i.id)
        # Add all nodes referenced in alternative relationships
        for r in self._ir.relationships:
            if r.type == RelationType.ALTERNATIVE:
                covered_ids.add(r.target)

        remaining = [
            n
            for n in self._ir.nodes
            if n.id not in covered_ids and n.type == NodeType.STATEMENT
        ]
        if remaining:
            sections.append("Additional context:")
            for n in remaining:
                sections.append(f"  - {n.content}")

        if not sections:
            return "(empty graph)"

        return "\n".join(sections)

    def _find_node(self, node_id: str) -> Optional[Node]:
        """Find node by ID."""
        return self._node_map.get(node_id)

    # =========================================================================
    # Mode 0 → Mode 3: Parse natural language (lossy)
    # =========================================================================

    @classmethod
    def from_mode0(
        cls, text: str, parser: Optional[ParserBridge] = None
    ) -> FallbackChain:
        """Parse natural language text to Mode 3 via FlowScript CLI.

        This is lossy — the parser does its best to extract structure from
        free text, but semantic relationships may be lost or inferred.
        """
        if parser is None:
            parser = ParserBridge()

        ir = parser.parse_text(text)
        return cls(ir)

"""
FlowScript Mode 3 LDP Delegate.

Server-side integration: receives LDP tasks and processes them using the
FlowScript query engine. Subclasses ``LdpDelegate`` from the ldp-protocol SDK.

Requires: pip install flowscript-ldp[ldp]

Usage::

    from flowscript_ldp.delegate import FlowScriptMode3Delegate

    delegate = FlowScriptMode3Delegate()

    # Run as HTTP server
    delegate.run(port=8090)

    # Or use programmatically
    output, confidence = await delegate.handle_task(
        "flowscript.tensions", {"ir": ir_dict}, "task-1"
    )
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from ldp_protocol import (
    LdpCapability,
    LdpEnvelope,
    LdpMessageBody,
    PayloadMode,
    QualityMetrics,
    TrustDomain,
)
from ldp_protocol.delegate import LdpDelegate

from . import __version__
from .adapter import (
    flowscript_alternatives,
    flowscript_blocked,
    flowscript_degrade,
    flowscript_tensions,
    flowscript_what_if,
    flowscript_why,
)
from .payload import FlowScriptPayload

# Skills exposed by this delegate, namespaced to avoid collisions in
# multi-delegate LdpRouter scenarios.
SKILLS: dict[str, dict[str, Any]] = {
    "flowscript.tensions": {
        "description": "Analyze tradeoffs in a FlowScript semantic graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ir": {"type": "object", "description": "FlowScript IR or Mode 3 envelope"},
            },
            "required": ["ir"],
        },
    },
    "flowscript.blocked": {
        "description": "Find blocked items with impact scores and transitive causes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ir": {"type": "object", "description": "FlowScript IR or Mode 3 envelope"},
            },
            "required": ["ir"],
        },
    },
    "flowscript.why": {
        "description": "Trace causal ancestry of a node in a FlowScript graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ir": {"type": "object", "description": "FlowScript IR or Mode 3 envelope"},
                "node_id": {"type": "string", "description": "Target node ID"},
            },
            "required": ["ir", "node_id"],
        },
    },
    "flowscript.what_if": {
        "description": "Analyze downstream impact of changing a node.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ir": {"type": "object", "description": "FlowScript IR or Mode 3 envelope"},
                "node_id": {"type": "string", "description": "Target node ID"},
            },
            "required": ["ir", "node_id"],
        },
    },
    "flowscript.alternatives": {
        "description": "Reconstruct a decision from alternatives in a FlowScript graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ir": {"type": "object", "description": "FlowScript IR or Mode 3 envelope"},
                "question_id": {"type": "string", "description": "Question node ID"},
            },
            "required": ["ir", "question_id"],
        },
    },
    "flowscript.degrade": {
        "description": "Degrade a Mode 3 payload to Mode 1 (semantic frame) or Mode 0 (text).",
        "input_schema": {
            "type": "object",
            "properties": {
                "ir": {"type": "object", "description": "FlowScript IR or Mode 3 envelope"},
                "target_mode": {"type": "integer", "enum": [0, 1], "default": 1},
            },
            "required": ["ir"],
        },
    },
}


class FlowScriptMode3Delegate(LdpDelegate):
    """LDP delegate that processes Mode 3 (Semantic Graph) tasks.

    Wraps the FlowScript query engine as a proper LDP delegate with
    identity, capability advertisement, session negotiation (including
    Mode 3 support), and task handling.

    Usage::

        delegate = FlowScriptMode3Delegate()
        delegate.run(port=8090)  # HTTP server

        # Or programmatically:
        output, confidence = await delegate.handle_task(
            "flowscript.tensions", {"ir": ir_dict}, "task-1"
        )

    All constructor kwargs are passed through to LdpDelegate, so you
    can override delegate_id, name, trust_domain, etc.
    """

    def __init__(self, **kwargs: Any) -> None:
        defaults: dict[str, Any] = {
            "delegate_id": "flowscript-ldp:mode3",
            "name": "FlowScript Mode 3",
            "description": (
                "LDP Mode 3 (Semantic Graphs) delegate using FlowScript IR. "
                "Provides 5 queryable coordination operations plus fallback degradation."
            ),
            "model_family": "flowscript",
            "model_version": __version__,
            "context_window": 0,  # not an LLM — graph operations
            "supported_payload_modes": [
                PayloadMode.SEMANTIC_GRAPH,
                PayloadMode.SEMANTIC_FRAME,
                PayloadMode.TEXT,
            ],
            "capabilities": [
                LdpCapability(
                    name=skill_name,
                    description=skill_info["description"],
                    input_schema=skill_info["input_schema"],
                    quality=QualityMetrics(
                        quality_score=1.0,  # deterministic
                        cost_per_call_usd=0.0,  # local computation
                        latency_p50_ms=1,  # sub-millisecond
                    ),
                )
                for skill_name, skill_info in SKILLS.items()
            ],
            "trust_domain": TrustDomain(
                name="flowscript", allow_cross_domain=True
            ),
        }
        # User kwargs override defaults
        merged = {**defaults, **kwargs}
        super().__init__(**merged)

    async def handle_task(
        self, skill: str, input_data: Any, task_id: str
    ) -> tuple[Any, float]:
        """Route a task to the appropriate FlowScript query operation.

        Args:
            skill: One of the ``flowscript.*`` skill names.
            input_data: Dict with ``ir`` key (raw IR or Mode 3 envelope)
                and optional ``node_id``/``question_id``/``target_mode``.
            task_id: Unique task identifier (from LDP protocol).

        Returns:
            Tuple of (output_dict, confidence). Confidence is always 1.0
            since these are deterministic graph operations.

        Raises:
            ValueError: Unknown skill or missing required arguments.
        """
        ir_json = self._extract_ir(input_data)

        if skill == "flowscript.tensions":
            return flowscript_tensions(ir_json), 1.0

        elif skill == "flowscript.blocked":
            return flowscript_blocked(ir_json), 1.0

        elif skill == "flowscript.why":
            node_id = self._require_arg(input_data, "node_id", skill)
            return flowscript_why(ir_json, node_id), 1.0

        elif skill == "flowscript.what_if":
            node_id = self._require_arg(input_data, "node_id", skill)
            return flowscript_what_if(ir_json, node_id), 1.0

        elif skill == "flowscript.alternatives":
            question_id = self._require_arg(input_data, "question_id", skill)
            return flowscript_alternatives(ir_json, question_id), 1.0

        elif skill == "flowscript.degrade":
            target_mode = input_data.get("target_mode", 1) if isinstance(input_data, dict) else 1
            result = flowscript_degrade(ir_json, target_mode)
            return {"degraded": result, "target_mode": target_mode}, 1.0

        else:
            raise ValueError(
                f"Unknown skill: {skill}. "
                f"Available: {', '.join(SKILLS.keys())}"
            )

    def _handle_session_propose(self, envelope: LdpEnvelope) -> LdpEnvelope:
        """Override to support Mode 3 negotiation.

        The ldp-protocol SDK's ``negotiate_payload_mode()`` filters on
        ``PayloadMode.is_implemented``, which returns False for
        SEMANTIC_GRAPH. Since this delegate IS the Mode 3 implementation,
        we bypass that gate when the initiator supports it.

        Note: This intentionally prefers SEMANTIC_GRAPH whenever the
        initiator supports it, regardless of where it appears in their
        preference list. A Mode 3 delegate exists to provide Mode 3 —
        if you can speak it, we will.
        """
        session_id = str(uuid4())

        # Parse initiator's supported modes, skipping any unknown values
        initiator_modes: list[PayloadMode] = []
        if envelope.body.config and "preferred_payload_modes" in envelope.body.config:
            for m in envelope.body.config["preferred_payload_modes"]:
                try:
                    initiator_modes.append(PayloadMode(m))
                except ValueError:
                    continue  # skip unknown/future mode values

        # If both sides support SEMANTIC_GRAPH, negotiate it directly
        if PayloadMode.SEMANTIC_GRAPH in initiator_modes:
            negotiated_mode = PayloadMode.SEMANTIC_GRAPH
        elif PayloadMode.SEMANTIC_FRAME in initiator_modes:
            negotiated_mode = PayloadMode.SEMANTIC_FRAME
        else:
            negotiated_mode = PayloadMode.TEXT

        return LdpEnvelope.create(
            session_id=session_id,
            from_id=self.identity.delegate_id,
            to_id=envelope.from_,
            body=LdpMessageBody.session_accept(
                session_id=session_id,
                negotiated_mode=negotiated_mode,
            ),
        )

    @staticmethod
    def _extract_ir(input_data: Any) -> dict[str, Any]:
        """Extract IR dict from various input formats.

        Accepts:
        - ``{"ir": {...}}`` — structured input with IR under "ir" key
        - Mode 3 envelope (has ``ldp_version`` key) — decoded automatically
        - Raw IR dict (has ``version`` + ``nodes`` keys) — used directly
        """
        if not isinstance(input_data, dict):
            raise ValueError(
                "input_data must be a dict containing 'ir' key, "
                "a Mode 3 envelope, or a raw IR dict"
            )

        # Structured input: {"ir": {...}, "node_id": "..."}
        if "ir" in input_data:
            ir_candidate = input_data["ir"]
            # The IR value might itself be an envelope
            if isinstance(ir_candidate, dict) and "ldp_version" in ir_candidate:
                payload = FlowScriptPayload.decode(ir_candidate)
                return payload.ir.model_dump(mode="json")
            return ir_candidate

        # Mode 3 envelope
        if "ldp_version" in input_data:
            payload = FlowScriptPayload.decode(input_data)
            return payload.ir.model_dump(mode="json")

        # Raw IR dict
        if "version" in input_data and "nodes" in input_data:
            return input_data

        raise ValueError(
            "Cannot extract IR from input_data. Expected 'ir' key, "
            "Mode 3 envelope (ldp_version), or raw IR (version + nodes)."
        )

    @staticmethod
    def _require_arg(input_data: Any, arg_name: str, skill: str) -> str:
        """Extract a required string argument from input_data."""
        if not isinstance(input_data, dict):
            raise ValueError(f"{skill} requires '{arg_name}' in input_data")
        value = input_data.get(arg_name)
        if value is None:
            raise ValueError(f"{skill} requires '{arg_name}' in input_data")
        return value

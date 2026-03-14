"""
JamJet Integration.

Two integration surfaces:

1. **Tool-based (works today):** JamJet @tool-decorated functions that wrap
   FlowScript query operations. Any JamJet workflow can call these as tool
   nodes. This is the primary integration path.

2. **Adapter pattern (forward-looking):** Standalone query dispatcher that
   follows the adapter pattern described in the LDP paper. Designed to plug
   into a future ProtocolAdapter interface when JamJet adds protocol-level
   extensibility. Usable standalone today as a query dispatcher.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from .fallback import FallbackChain
from .ir import IR
from .payload import FlowScriptPayload
from .query import QueryEngine

# =============================================================================
# Tool-based integration (works with JamJet v0.1.x today)
# =============================================================================

# These functions can be registered as JamJet tools via the @tool decorator.
# Import and use them in your JamJet workflow:
#
#   from jamjet import tool
#   from flowscript_ldp.adapter import (
#       flowscript_tensions, flowscript_blocked,
#       flowscript_why, flowscript_what_if, flowscript_alternatives,
#   )
#
# Then reference them in Agent or Workflow tool lists.


def flowscript_tensions(ir_json: dict[str, Any]) -> dict[str, Any]:
    """Analyze tradeoffs in a FlowScript semantic graph.

    Returns all tension relationships grouped by axis, with metadata
    about total tensions and most common tradeoff dimension.
    """
    payload = FlowScriptPayload.from_dict(ir_json)
    result = payload.query.tensions()
    return {"tensions": result.metadata}


def flowscript_blocked(ir_json: dict[str, Any]) -> dict[str, Any]:
    """Find blocked items in a FlowScript semantic graph.

    Returns all blocked nodes with impact scores, transitive causes,
    and days-blocked tracking.
    """
    payload = FlowScriptPayload.from_dict(ir_json)
    result = payload.query.blocked()
    return {
        "blockers": [
            {
                "content": b.node["content"],
                "reason": b.blocked_state["reason"],
                "impact_score": b.impact_score,
                "days_blocked": b.blocked_state["days_blocked"],
            }
            for b in result.blockers
        ],
        "metadata": result.metadata,
    }


def flowscript_why(ir_json: dict[str, Any], node_id: str) -> dict[str, Any]:
    """Trace causal ancestry of a node in a FlowScript semantic graph.

    Returns the root cause and causal chain explaining why a node exists.
    """
    payload = FlowScriptPayload.from_dict(ir_json)
    result = payload.query.why(node_id, format="minimal")
    return asdict(result)


def flowscript_what_if(ir_json: dict[str, Any], node_id: str) -> dict[str, Any]:
    """Analyze downstream impact of changing a node in a FlowScript graph.

    Returns impact summary with benefits, risks, and key tradeoffs.
    """
    payload = FlowScriptPayload.from_dict(ir_json)
    result = payload.query.what_if(node_id, format="summary")
    return asdict(result)


def flowscript_alternatives(
    ir_json: dict[str, Any], question_id: str
) -> dict[str, Any]:
    """Reconstruct a decision from a FlowScript semantic graph.

    Returns all alternatives considered, which was chosen, and why.
    """
    payload = FlowScriptPayload.from_dict(ir_json)
    result = payload.query.alternatives(question_id, format="simple")
    return asdict(result)


def flowscript_degrade(
    ir_json: dict[str, Any], target_mode: int = 1
) -> dict[str, Any] | str:
    """Degrade a FlowScript Mode 3 payload to Mode 1 or Mode 0.

    Mode 1: Structured semantic frame (JSON).
    Mode 0: Natural language prose (string).
    """
    ir = IR.model_validate(ir_json)
    fallback = FallbackChain(ir)
    if target_mode == 0:
        return fallback.to_mode0()
    return fallback.to_mode1()


# =============================================================================
# Adapter pattern (standalone dispatcher + future ProtocolAdapter hook)
# =============================================================================


class FlowScriptMode3Adapter:
    """FlowScript Mode 3 query dispatcher.

    Standalone adapter that processes Mode 3 payloads with optional query
    execution and fallback degradation. Follows the adapter pattern
    described in the LDP paper (arXiv:2603.08852) for protocol-level
    integration.

    Currently usable as a standalone query dispatcher. Designed to be
    compatible with a future JamJet ProtocolAdapter interface when
    protocol-level extensibility is added to the runtime.
    """

    ADAPTER_NAME = "flowscript-mode3"
    SUPPORTED_MODES = [0, 1, 3]
    SUPPORTED_QUERIES = ["why", "whatIf", "tensions", "blocked", "alternatives"]

    def discover(self) -> dict[str, Any]:
        """Return adapter capabilities."""
        return {
            "name": self.ADAPTER_NAME,
            "version": "0.1.0",
            "protocol": "ldp",
            "supported_modes": self.SUPPORTED_MODES,
            "preferred_mode": 3,
            "payload_format": "flowscript-ir",
            "capabilities": self.SUPPORTED_QUERIES,
            "ir_version": "1.0.0",
        }

    def invoke(
        self,
        payload_data: dict[str, Any],
        *,
        query: Optional[str] = None,
        query_args: Optional[dict[str, Any]] = None,
        fallback_mode: Optional[int] = None,
    ) -> dict[str, Any]:
        """Process a Mode 3 payload.

        Args:
            payload_data: LDP Mode 3 envelope or raw IR dict
            query: Query to run (why, whatIf, tensions, blocked, alternatives)
            query_args: Arguments for the query (e.g., node_id for why/whatIf)
            fallback_mode: Degrade output to this mode (1 or 0)

        Returns:
            Query results, degraded payload, or IR stats
        """
        # Decode payload
        if "ldp_version" in payload_data:
            payload = FlowScriptPayload.decode(payload_data)
        else:
            payload = FlowScriptPayload.from_dict(payload_data)

        result: dict[str, Any] = {"adapter": self.ADAPTER_NAME, "mode": 3}

        # Run query if specified
        if query:
            query_result = self._run_query(payload.query, query, query_args or {})
            result["query"] = query
            result["result"] = query_result

        # Apply fallback if requested
        if fallback_mode is not None:
            fallback = FallbackChain(payload.ir)
            if fallback_mode == 1:
                result["fallback"] = fallback.to_mode1()
                result["mode"] = 1
            elif fallback_mode == 0:
                result["fallback"] = fallback.to_mode0()
                result["mode"] = 0

        # Include IR stats if no query or fallback was requested
        if "result" not in result and "fallback" not in result:
            result["ir_stats"] = {
                "nodes": len(payload.ir.nodes),
                "relationships": len(payload.ir.relationships),
                "states": len(payload.ir.states),
            }

        return result

    def _run_query(
        self, engine: QueryEngine, query: str, args: dict[str, Any]
    ) -> Any:
        """Dispatch a query to the engine."""
        if query == "tensions":
            r = engine.tensions(**args)
            return {"metadata": r.metadata}
        elif query == "blocked":
            r = engine.blocked(**args)
            return {
                "blockers": [
                    {
                        "content": b.node["content"],
                        "reason": b.blocked_state["reason"],
                        "impact_score": b.impact_score,
                    }
                    for b in r.blockers
                ],
                "metadata": r.metadata,
            }
        elif query == "why":
            node_id = args.get("node_id")
            if not node_id:
                raise ValueError("why query requires node_id argument")
            r = engine.why(node_id, format="minimal")
            return asdict(r)
        elif query in ("whatIf", "what_if"):
            node_id = args.get("node_id")
            if not node_id:
                raise ValueError("whatIf query requires node_id argument")
            r = engine.what_if(node_id, format="summary")
            return asdict(r)
        elif query == "alternatives":
            question_id = args.get("question_id")
            if not question_id:
                raise ValueError("alternatives query requires question_id argument")
            r = engine.alternatives(question_id, format="simple")
            return asdict(r)
        else:
            raise ValueError(f"Unknown query: {query}")

    def status(self) -> dict[str, str]:
        """Return adapter status."""
        return {"status": "ready", "adapter": self.ADAPTER_NAME}

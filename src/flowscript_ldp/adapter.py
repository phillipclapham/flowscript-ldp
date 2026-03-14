"""
JamJet ProtocolAdapter hook.

Provides the interface for JamJet's ProtocolAdapter pattern to integrate
FlowScript Mode 3 payloads into agent workflows.

This is the adapter that would register alongside MCP and A2A adapters
in a JamJet runtime, enabling FlowScript semantic graph payloads as a
first-class workflow node type.
"""

from __future__ import annotations

from typing import Any, Optional

from .fallback import FallbackChain
from .ir import IR
from .payload import FlowScriptPayload
from .query import QueryEngine


class FlowScriptMode3Adapter:
    """JamJet ProtocolAdapter for FlowScript Mode 3 payloads.

    Implements the adapter pattern for JamJet's plugin system. In a full
    JamJet integration, this would register via the ProtocolAdapter trait
    for discovery, invocation, streaming, status, and cancellation.

    Usage in JamJet workflow YAML:
        nodes:
          analyze:
            type: flowscript_mode3
            input_mode: 3
            query: tensions
            output_key: tradeoffs
            fallback_mode: 1
            next: synthesize
    """

    ADAPTER_NAME = "flowscript-mode3"
    SUPPORTED_MODES = [0, 1, 3]
    SUPPORTED_QUERIES = ["why", "whatIf", "tensions", "blocked", "alternatives"]

    def discover(self) -> dict[str, Any]:
        """Return adapter capabilities for JamJet discovery."""
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
        """Process a Mode 3 payload through the adapter.

        Args:
            payload_data: LDP Mode 3 envelope or raw IR dict
            query: Optional query to run (why, whatIf, tensions, blocked, alternatives)
            query_args: Arguments for the query (e.g., node_id for why/whatIf)
            fallback_mode: If set, degrade output to this mode (1 or 0)

        Returns:
            Query results or degraded payload
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

        # Always include the original IR reference
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
            return r.__dict__ if hasattr(r, "__dict__") else r
        elif query in ("whatIf", "what_if"):
            node_id = args.get("node_id")
            if not node_id:
                raise ValueError("whatIf query requires node_id argument")
            r = engine.what_if(node_id, format="summary")
            return r.__dict__ if hasattr(r, "__dict__") else r
        elif query == "alternatives":
            question_id = args.get("question_id")
            if not question_id:
                raise ValueError("alternatives query requires question_id argument")
            r = engine.alternatives(question_id, format="simple")
            return r.__dict__ if hasattr(r, "__dict__") else r
        else:
            raise ValueError(f"Unknown query: {query}")

    def status(self) -> dict[str, str]:
        """Return adapter status."""
        return {"status": "ready", "adapter": self.ADAPTER_NAME}

    def cancel(self) -> None:
        """Cancel any in-progress operation. No-op for sync adapter."""
        pass

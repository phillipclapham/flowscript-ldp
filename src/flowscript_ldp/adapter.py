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

from . import __version__
from .fallback import FallbackChain
from .ir import IR
from .payload import FlowScriptPayload
from .query import QueryEngine

# =============================================================================
# Tool functions (sync — usable standalone or via get_jamjet_tools())
# =============================================================================

# These functions contain the query logic. They're sync for direct use.
# For JamJet integration, use get_jamjet_tools() which wraps them as
# async @tool-decorated functions that JamJet's Agent requires.
#
#   from flowscript_ldp.adapter import get_jamjet_tools
#   tools = get_jamjet_tools()
#   agent = Agent("analyst", model="...", tools=tools, instructions="...")


def flowscript_tensions(ir_json: dict[str, Any]) -> dict[str, Any]:
    """Analyze tradeoffs in a FlowScript semantic graph.

    Returns all tension relationships grouped by axis, with the source
    and target content of each tension pair, plus summary metadata.
    """
    payload = FlowScriptPayload.from_dict(ir_json)
    result = payload.query.tensions()
    tensions_detail: list[dict[str, str]] = []
    if result.tensions_by_axis:
        for axis, details in result.tensions_by_axis.items():
            for d in details:
                tensions_detail.append({
                    "axis": axis,
                    "source": d.source["content"],
                    "target": d.target["content"],
                })
    return {"tensions": tensions_detail, "metadata": result.metadata}


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
# JamJet tool registration (async wrappers for JamJet @tool decorator)
# =============================================================================


def get_jamjet_tools() -> list:
    """Return all FlowScript query operations as JamJet @tool-decorated functions.

    JamJet requires async tool functions decorated with @jamjet.tool.
    This function lazily imports jamjet and returns ready-to-use tools.

    Usage::

        from jamjet import Agent
        from flowscript_ldp.adapter import get_jamjet_tools

        agent = Agent(
            "analyst",
            model="claude-haiku-4-5-20251001",
            tools=get_jamjet_tools(),
            instructions="Analyze the semantic graph.",
        )
        result = await agent.run(f"Analyze: {ir_json}")
    """
    try:
        from jamjet import tool
    except ImportError:
        raise ImportError(
            "JamJet is required for tool integration. "
            "Install it with: pip install jamjet"
        )

    @tool
    async def flowscript_tensions_tool(ir_json: dict[str, Any]) -> dict[str, Any]:
        """Analyze tradeoffs in a FlowScript semantic graph."""
        return flowscript_tensions(ir_json)

    @tool
    async def flowscript_blocked_tool(ir_json: dict[str, Any]) -> dict[str, Any]:
        """Find blocked items in a FlowScript semantic graph."""
        return flowscript_blocked(ir_json)

    @tool
    async def flowscript_why_tool(ir_json: dict[str, Any], node_id: str) -> dict[str, Any]:
        """Trace causal ancestry of a node in a FlowScript semantic graph."""
        return flowscript_why(ir_json, node_id)

    @tool
    async def flowscript_what_if_tool(ir_json: dict[str, Any], node_id: str) -> dict[str, Any]:
        """Analyze downstream impact of changing a node in a FlowScript graph."""
        return flowscript_what_if(ir_json, node_id)

    @tool
    async def flowscript_alternatives_tool(ir_json: dict[str, Any], question_id: str) -> dict[str, Any]:
        """Reconstruct a decision from a FlowScript semantic graph."""
        return flowscript_alternatives(ir_json, question_id)

    @tool
    async def flowscript_degrade_tool(ir_json: dict[str, Any], target_mode: int = 1) -> dict[str, Any] | str:
        """Degrade a FlowScript Mode 3 payload to Mode 1 or Mode 0."""
        return flowscript_degrade(ir_json, target_mode)

    return [
        flowscript_tensions_tool,
        flowscript_blocked_tool,
        flowscript_why_tool,
        flowscript_what_if_tool,
        flowscript_alternatives_tool,
        flowscript_degrade_tool,
    ]


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
            "version": __version__,
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
            ir_json = payload.ir.model_dump(mode="json")
            query_result = self._run_query(ir_json, query, query_args or {})
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
        self, ir_json: dict[str, Any], query: str, args: dict[str, Any]
    ) -> Any:
        """Dispatch a query to the engine.

        Delegates to the standalone tool functions to ensure a single
        formatting path for all query results.
        """
        if query == "tensions":
            return flowscript_tensions(ir_json)
        elif query == "blocked":
            return flowscript_blocked(ir_json)
        elif query == "why":
            node_id = args.get("node_id")
            if not node_id:
                raise ValueError("why query requires node_id argument")
            return flowscript_why(ir_json, node_id)
        elif query in ("whatIf", "what_if"):
            node_id = args.get("node_id")
            if not node_id:
                raise ValueError("whatIf query requires node_id argument")
            return flowscript_what_if(ir_json, node_id)
        elif query == "alternatives":
            question_id = args.get("question_id")
            if not question_id:
                raise ValueError("alternatives query requires question_id argument")
            return flowscript_alternatives(ir_json, question_id)
        else:
            raise ValueError(f"Unknown query: {query}")

    def status(self) -> dict[str, str]:
        """Return adapter status."""
        return {"status": "ready", "adapter": self.ADAPTER_NAME}


# =============================================================================
# JamJet ProtocolAdapter for LDP (requires jamjet>=0.2.0 + ldp-protocol)
# =============================================================================

# Conditional base class: inherit from ProtocolAdapter when jamjet is installed,
# fall back to object when it isn't. This keeps the module importable without
# jamjet while providing proper subclass behavior when available.
try:
    from jamjet.protocols.adapter import ProtocolAdapter as _LdpAdapterBase
except ImportError:
    _LdpAdapterBase = object  # type: ignore[misc,assignment]


class FlowScriptLdpAdapter(_LdpAdapterBase):
    """JamJet ProtocolAdapter that bridges to LDP delegates via LdpClient.

    Enables JamJet workflows to discover and invoke LDP delegates
    (including FlowScriptMode3Delegate) through the protocol registry.

    Requires: ``pip install flowscript-ldp[all]``

    Usage::

        from flowscript_ldp.adapter import FlowScriptLdpAdapter

        # Register with JamJet's protocol registry
        FlowScriptLdpAdapter.register()

        # Or use directly
        adapter = FlowScriptLdpAdapter()
        caps = await adapter.discover("http://localhost:8090")
        handle = await adapter.invoke("http://localhost:8090", task)
        result = await adapter.status("http://localhost:8090", handle.task_id)
    """

    ADAPTER_NAME = "ldp"
    URL_PREFIXES = ["ldp://", "ldp+flowscript://"]

    def __init__(self) -> None:
        try:
            from jamjet.protocols.adapter import ProtocolAdapter  # noqa: F401
            from ldp_protocol import LdpClient  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Both jamjet>=0.2.0 and ldp-protocol are required for "
                "FlowScriptLdpAdapter. Install with: pip install flowscript-ldp[all]"
            ) from e

        self._client = LdpClient()
        # LDP tasks complete synchronously in invoke(), but JamJet's
        # ProtocolAdapter splits invoke/status. We cache results here.
        # Bounded to prevent memory leaks in long-running processes.
        self._results: dict[str, dict] = {}
        self._max_cached = 1000

    async def discover(self, url: str):
        """Discover remote delegate capabilities via LDP identity endpoint.

        Maps LDP ``LdpIdentityCard`` to JamJet ``RemoteCapabilities``.
        """
        from jamjet.protocols.adapter import RemoteCapabilities, RemoteSkill

        identity = await self._client.discover(url)
        return RemoteCapabilities(
            name=identity.name,
            description=identity.description or "",
            skills=[
                RemoteSkill(
                    name=cap.name,
                    description=cap.description,
                    input_schema=cap.input_schema,
                    output_schema=cap.output_schema,
                )
                for cap in identity.capabilities
            ],
            protocols=["ldp"],
        )

    async def invoke(self, url: str, task):
        """Submit a task to an LDP delegate and cache the result.

        LDP tasks are synchronous (request-response), so the result is
        available immediately. We cache it for retrieval via ``status()``.

        Args:
            url: Delegate endpoint URL.
            task: JamJet ``TaskRequest`` with skill, input, etc.

        Returns:
            JamJet ``TaskHandle`` with task_id and remote_url.
        """
        from jamjet.protocols.adapter import TaskHandle

        result = await self._client.submit_task(
            url,
            skill=task.skill,
            input_data=task.input if isinstance(task.input, dict) else {"text": task.input},
        )

        task_id = result.get("task_id", "")

        # Evict oldest entry if cache is full
        if len(self._results) >= self._max_cached:
            oldest = next(iter(self._results))
            del self._results[oldest]

        self._results[task_id] = result

        return TaskHandle(task_id=task_id, remote_url=url)

    async def stream(self, url: str, task):
        """Stream task events (not yet supported by LDP).

        LDP is currently request-response only. Calling this method
        returns an async iterator that raises ``NotImplementedError``
        on the first iteration.
        """
        raise NotImplementedError(
            "LDP streaming is not yet available. Use invoke() for "
            "request-response task submission."
        )
        # AsyncIterator yield to satisfy type checker
        yield  # pragma: no cover

    async def status(self, url: str, task_id: str):
        """Check task status. Returns cached result from invoke().

        LDP tasks complete synchronously during invoke(), so status
        always returns the cached result.
        """
        from jamjet.protocols.adapter import TaskStatus

        result = self._results.get(task_id)
        if result is not None:
            return TaskStatus.completed(output=result.get("output"))
        return TaskStatus.submitted()

    async def cancel(self, url: str, task_id: str) -> None:
        """Cancel a task (no-op for LDP synchronous tasks)."""
        self._results.pop(task_id, None)

    @classmethod
    def register(cls):
        """Register this adapter with JamJet's default ProtocolRegistry.

        After calling this, JamJet can route to LDP delegates via
        ``ldp://`` or ``ldp+flowscript://`` URL prefixes.

        Usage::

            FlowScriptLdpAdapter.register()
            # Now JamJet workflows can use ldp:// URLs
        """
        from jamjet.protocols.registry import get_registry

        registry = get_registry()
        adapter = cls()
        registry.register(
            cls.ADAPTER_NAME,
            adapter,
            url_prefixes=cls.URL_PREFIXES,
        )

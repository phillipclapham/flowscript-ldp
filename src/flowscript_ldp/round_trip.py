"""
Round-trip verification utilities.

Verifies that FlowScript IR survives encode/decode cycles through LDP
payload format without losing queryable structure.
"""

from __future__ import annotations

from typing import Any

from .fallback import FallbackChain
from .ir import IR
from .payload import FlowScriptPayload
from .query import QueryEngine


def verify_mode3_round_trip(ir: IR) -> dict[str, Any]:
    """Verify Mode 3 encode → decode preserves IR structure.

    Returns verification report with pass/fail and details.
    """
    # Encode
    payload = FlowScriptPayload(ir)
    encoded = payload.encode()

    # Decode
    decoded_payload = FlowScriptPayload.decode(encoded)
    decoded_ir = decoded_payload.ir

    # Compare
    checks = {
        "version_match": ir.version == decoded_ir.version,
        "node_count_match": len(ir.nodes) == len(decoded_ir.nodes),
        "relationship_count_match": len(ir.relationships)
        == len(decoded_ir.relationships),
        "state_count_match": len(ir.states) == len(decoded_ir.states),
        "node_ids_match": {n.id for n in ir.nodes}
        == {n.id for n in decoded_ir.nodes},
        "relationship_ids_match": {r.id for r in ir.relationships}
        == {r.id for r in decoded_ir.relationships},
        "node_types_preserved": all(
            any(
                dn.id == n.id and dn.type == n.type for dn in decoded_ir.nodes
            )
            for n in ir.nodes
        ),
        "node_content_preserved": all(
            any(
                dn.id == n.id and dn.content == n.content
                for dn in decoded_ir.nodes
            )
            for n in ir.nodes
        ),
    }

    all_passed = all(checks.values())

    return {
        "passed": all_passed,
        "checks": checks,
        "original_stats": {
            "nodes": len(ir.nodes),
            "relationships": len(ir.relationships),
            "states": len(ir.states),
        },
        "decoded_stats": {
            "nodes": len(decoded_ir.nodes),
            "relationships": len(decoded_ir.relationships),
            "states": len(decoded_ir.states),
        },
    }


def verify_queries_on_decoded(ir: IR) -> dict[str, Any]:
    """Verify all 5 query operations work on decoded payloads."""
    payload = FlowScriptPayload(ir)
    encoded = payload.encode()
    decoded = FlowScriptPayload.decode(encoded)
    engine = decoded.query

    results: dict[str, Any] = {}

    # Test each query operation
    try:
        tensions_result = engine.tensions()
        results["tensions"] = {
            "passed": True,
            "total": tensions_result.metadata.get("total_tensions", 0),
        }
    except Exception as e:
        results["tensions"] = {"passed": False, "error": str(e)}

    try:
        blocked_result = engine.blocked()
        results["blocked"] = {
            "passed": True,
            "total": blocked_result.metadata.get("total_blockers", 0),
        }
    except Exception as e:
        results["blocked"] = {"passed": False, "error": str(e)}

    # Test why and what_if on first node (if exists)
    if ir.nodes:
        first_id = ir.nodes[0].id
        try:
            engine.why(first_id)
            results["why"] = {"passed": True}
        except Exception as e:
            results["why"] = {"passed": False, "error": str(e)}

        try:
            engine.what_if(first_id)
            results["what_if"] = {"passed": True}
        except Exception as e:
            results["what_if"] = {"passed": False, "error": str(e)}

    # Test alternatives on first question node
    question_nodes = [n for n in ir.nodes if n.type.value == "question"]
    if question_nodes:
        try:
            engine.alternatives(question_nodes[0].id)
            results["alternatives"] = {"passed": True}
        except Exception as e:
            results["alternatives"] = {"passed": False, "error": str(e)}

    return {
        "all_passed": all(r.get("passed", False) for r in results.values()),
        "queries": results,
    }


def verify_fallback_chain(ir: IR) -> dict[str, Any]:
    """Verify Mode 3 → Mode 1 → Mode 0 degradation produces valid output."""
    fallback = FallbackChain(ir)

    results: dict[str, Any] = {}

    # Mode 3 → Mode 1
    try:
        mode1 = fallback.to_mode1()
        results["mode3_to_mode1"] = {
            "passed": True,
            "task_type": mode1.get("task_type"),
            "has_instruction": bool(mode1.get("instruction")),
            "has_input": bool(mode1.get("input")),
            "label_count": len(mode1.get("labels", [])),
        }
    except Exception as e:
        results["mode3_to_mode1"] = {"passed": False, "error": str(e)}

    # Mode 3 → Mode 0
    try:
        mode0 = fallback.to_mode0()
        results["mode3_to_mode0"] = {
            "passed": True,
            "length": len(mode0),
            "is_readable": len(mode0) > 10,
        }
    except Exception as e:
        results["mode3_to_mode0"] = {"passed": False, "error": str(e)}

    return {
        "all_passed": all(r.get("passed", False) for r in results.values()),
        "fallbacks": results,
    }

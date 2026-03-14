"""Tests for JamJet adapter and tool functions."""

import pytest

from flowscript_ldp.adapter import (
    FlowScriptMode3Adapter,
    flowscript_tensions,
    flowscript_blocked,
    flowscript_why,
    flowscript_what_if,
    flowscript_alternatives,
    flowscript_degrade,
)
from flowscript_ldp.payload import FlowScriptPayload


class TestDiscover:
    def test_discover_returns_capabilities(self):
        adapter = FlowScriptMode3Adapter()
        info = adapter.discover()
        assert info["name"] == "flowscript-mode3"
        assert info["protocol"] == "ldp"
        assert 3 in info["supported_modes"]
        assert "why" in info["capabilities"]

    def test_status(self):
        adapter = FlowScriptMode3Adapter()
        assert adapter.status()["status"] == "ready"


class TestInvoke:
    def test_invoke_with_envelope(self, decision_ir):
        adapter = FlowScriptMode3Adapter()
        payload = FlowScriptPayload(decision_ir)
        envelope = payload.encode()
        result = adapter.invoke(envelope)
        assert result["adapter"] == "flowscript-mode3"
        assert result["mode"] == 3
        assert result["ir_stats"]["nodes"] == 5

    def test_invoke_with_raw_ir(self, decision_ir):
        adapter = FlowScriptMode3Adapter()
        ir_dict = decision_ir.model_dump(mode="json")
        result = adapter.invoke(ir_dict)
        assert result["mode"] == 3

    def test_invoke_with_tensions_query(self, decision_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(decision_ir).encode()
        result = adapter.invoke(envelope, query="tensions")
        assert result["query"] == "tensions"
        assert result["result"]["metadata"]["total_tensions"] == 1

    def test_invoke_with_blocked_query(self, blocker_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(blocker_ir).encode()
        result = adapter.invoke(envelope, query="blocked")
        assert len(result["result"]["blockers"]) == 1
        assert result["result"]["blockers"][0]["reason"] == "waiting on vendor"

    def test_invoke_with_why_query(self, simple_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(simple_ir).encode()
        node_id = simple_ir.nodes[1].id  # "effect" node
        result = adapter.invoke(envelope, query="why", query_args={"node_id": node_id})
        assert result["result"]["root_cause"] == "root cause"

    def test_invoke_with_what_if_query(self, simple_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(simple_ir).encode()
        node_id = simple_ir.nodes[0].id  # "root cause" node
        result = adapter.invoke(envelope, query="whatIf", query_args={"node_id": node_id})
        assert "impact_summary" in result["result"]

    def test_invoke_with_alternatives_query(self, decision_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(decision_ir).encode()
        q_id = "q" * 64
        result = adapter.invoke(envelope, query="alternatives", query_args={"question_id": q_id})
        assert result["result"]["chosen"] == "PostgreSQL"

    def test_invoke_with_fallback_mode1(self, decision_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(decision_ir).encode()
        result = adapter.invoke(envelope, fallback_mode=1)
        assert result["mode"] == 1
        assert "task_type" in result["fallback"]

    def test_invoke_with_fallback_mode0(self, decision_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(decision_ir).encode()
        result = adapter.invoke(envelope, fallback_mode=0)
        assert result["mode"] == 0
        assert isinstance(result["fallback"], str)

    def test_invoke_with_query_and_fallback(self, decision_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(decision_ir).encode()
        result = adapter.invoke(envelope, query="tensions", fallback_mode=1)
        assert "result" in result
        assert "fallback" in result


class TestInvokeErrors:
    def test_unknown_query(self, simple_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(simple_ir).encode()
        with pytest.raises(ValueError, match="Unknown query"):
            adapter.invoke(envelope, query="nonexistent")

    def test_why_without_node_id(self, simple_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(simple_ir).encode()
        with pytest.raises(ValueError, match="node_id"):
            adapter.invoke(envelope, query="why")

    def test_what_if_without_node_id(self, simple_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(simple_ir).encode()
        with pytest.raises(ValueError, match="node_id"):
            adapter.invoke(envelope, query="whatIf")

    def test_alternatives_without_question_id(self, simple_ir):
        adapter = FlowScriptMode3Adapter()
        envelope = FlowScriptPayload(simple_ir).encode()
        with pytest.raises(ValueError, match="question_id"):
            adapter.invoke(envelope, query="alternatives")


class TestToolFunctions:
    """Tests for JamJet @tool-compatible functions."""

    def test_flowscript_tensions(self, decision_ir):
        ir_dict = decision_ir.model_dump(mode="json")
        result = flowscript_tensions(ir_dict)
        assert result["tensions"]["total_tensions"] == 1

    def test_flowscript_blocked(self, blocker_ir):
        ir_dict = blocker_ir.model_dump(mode="json")
        result = flowscript_blocked(ir_dict)
        assert len(result["blockers"]) == 1
        assert result["blockers"][0]["reason"] == "waiting on vendor"

    def test_flowscript_why(self, simple_ir):
        ir_dict = simple_ir.model_dump(mode="json")
        node_id = simple_ir.nodes[1].id
        result = flowscript_why(ir_dict, node_id)
        assert result["root_cause"] == "root cause"

    def test_flowscript_what_if(self, simple_ir):
        ir_dict = simple_ir.model_dump(mode="json")
        node_id = simple_ir.nodes[0].id
        result = flowscript_what_if(ir_dict, node_id)
        assert "impact_summary" in result

    def test_flowscript_alternatives(self, decision_ir):
        ir_dict = decision_ir.model_dump(mode="json")
        q_id = "q" * 64
        result = flowscript_alternatives(ir_dict, q_id)
        assert result["chosen"] == "PostgreSQL"

    def test_flowscript_degrade_mode1(self, decision_ir):
        ir_dict = decision_ir.model_dump(mode="json")
        result = flowscript_degrade(ir_dict, target_mode=1)
        assert isinstance(result, dict)
        assert result["task_type"] == "decision_analysis"

    def test_flowscript_degrade_mode0(self, decision_ir):
        ir_dict = decision_ir.model_dump(mode="json")
        result = flowscript_degrade(ir_dict, target_mode=0)
        assert isinstance(result, str)
        assert "which database?" in result


class TestRepr:
    """Tests for __repr__ on result types."""

    def test_tensions_repr(self, decision_ir):
        engine = FlowScriptPayload(decision_ir).query
        result = engine.tensions()
        r = repr(result)
        assert "1 tension" in r
        assert "consistency vs speed" in r

    def test_blocked_repr(self, blocker_ir):
        engine = FlowScriptPayload(blocker_ir).query
        result = engine.blocked()
        r = repr(result)
        assert "1 blocker" in r

    def test_causal_ancestry_repr(self, simple_ir):
        engine = FlowScriptPayload(simple_ir).query
        result = engine.why("bbb" + "0" * 61)
        r = repr(result)
        assert "CausalAncestry" in r

    def test_impact_analysis_repr(self, simple_ir):
        engine = FlowScriptPayload(simple_ir).query
        result = engine.what_if("aaa" + "0" * 61)
        r = repr(result)
        assert "ImpactAnalysis" in r

    def test_alternatives_repr(self, decision_ir):
        engine = FlowScriptPayload(decision_ir).query
        result = engine.alternatives("q" * 64, format="simple")
        r = repr(result)
        assert "PostgreSQL" in r

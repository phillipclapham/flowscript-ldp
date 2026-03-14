"""Tests for FlowScriptMode3Delegate (LDP server-side integration)."""

import pytest

ldp_protocol = pytest.importorskip("ldp_protocol")

from ldp_protocol import (
    LdpEnvelope,
    LdpMessageBody,
    PayloadMode,
)

from flowscript_ldp.delegate import FlowScriptMode3Delegate, SKILLS
from flowscript_ldp.payload import FlowScriptPayload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ir_dict(ir):
    """Convert an IR fixture to a JSON-compatible dict."""
    return ir.model_dump(mode="json")


def _structured_input(ir, **extra):
    """Build structured input_data: {"ir": {...}, ...extra}."""
    d = {"ir": _ir_dict(ir)}
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# Skill dispatch tests
# ---------------------------------------------------------------------------


class TestDelegateSkills:
    """Test each skill via handle_task()."""

    @pytest.mark.asyncio
    async def test_tensions(self, decision_ir):
        delegate = FlowScriptMode3Delegate()
        result, confidence = await delegate.handle_task(
            "flowscript.tensions", _structured_input(decision_ir), "t-1"
        )
        assert confidence == 1.0
        assert result["metadata"]["total_tensions"] == 1
        assert len(result["tensions"]) == 1
        assert result["tensions"][0]["axis"] == "consistency vs speed"

    @pytest.mark.asyncio
    async def test_blocked(self, blocker_ir):
        delegate = FlowScriptMode3Delegate()
        result, confidence = await delegate.handle_task(
            "flowscript.blocked", _structured_input(blocker_ir), "t-2"
        )
        assert confidence == 1.0
        assert len(result["blockers"]) == 1
        assert result["blockers"][0]["reason"] == "waiting on vendor"

    @pytest.mark.asyncio
    async def test_why(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        node_id = simple_ir.nodes[1].id  # "effect" node
        result, confidence = await delegate.handle_task(
            "flowscript.why",
            _structured_input(simple_ir, node_id=node_id),
            "t-3",
        )
        assert confidence == 1.0
        assert result["root_cause"] == "root cause"

    @pytest.mark.asyncio
    async def test_what_if(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        node_id = simple_ir.nodes[0].id  # "root cause" node
        result, confidence = await delegate.handle_task(
            "flowscript.what_if",
            _structured_input(simple_ir, node_id=node_id),
            "t-4",
        )
        assert confidence == 1.0
        assert "impact_summary" in result

    @pytest.mark.asyncio
    async def test_alternatives(self, decision_ir):
        delegate = FlowScriptMode3Delegate()
        question_id = "q" * 64  # from decision_ir fixture
        result, confidence = await delegate.handle_task(
            "flowscript.alternatives",
            _structured_input(decision_ir, question_id=question_id),
            "t-5",
        )
        assert confidence == 1.0
        assert len(result["options_considered"]) == 2

    @pytest.mark.asyncio
    async def test_degrade_mode1(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        result, confidence = await delegate.handle_task(
            "flowscript.degrade",
            _structured_input(simple_ir, target_mode=1),
            "t-6",
        )
        assert confidence == 1.0
        assert result["target_mode"] == 1
        assert isinstance(result["degraded"], dict)
        assert "task_type" in result["degraded"]

    @pytest.mark.asyncio
    async def test_degrade_mode0(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        result, confidence = await delegate.handle_task(
            "flowscript.degrade",
            _structured_input(simple_ir, target_mode=0),
            "t-7",
        )
        assert confidence == 1.0
        assert result["target_mode"] == 0
        assert isinstance(result["degraded"], str)


# ---------------------------------------------------------------------------
# Input format flexibility
# ---------------------------------------------------------------------------


class TestDelegateInputFormats:
    """Verify handle_task works with all accepted input formats."""

    @pytest.mark.asyncio
    async def test_raw_ir_dict(self, simple_ir):
        """Raw IR dict (no 'ir' wrapper key)."""
        delegate = FlowScriptMode3Delegate()
        result, _ = await delegate.handle_task(
            "flowscript.tensions", _ir_dict(simple_ir), "t-raw"
        )
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_mode3_envelope(self, decision_ir):
        """Mode 3 envelope (has ldp_version key)."""
        delegate = FlowScriptMode3Delegate()
        envelope = FlowScriptPayload(decision_ir).encode()
        result, _ = await delegate.handle_task(
            "flowscript.tensions", envelope, "t-env"
        )
        assert result["metadata"]["total_tensions"] == 1

    @pytest.mark.asyncio
    async def test_structured_with_envelope_ir(self, decision_ir):
        """Structured input where 'ir' value is a Mode 3 envelope."""
        delegate = FlowScriptMode3Delegate()
        envelope = FlowScriptPayload(decision_ir).encode()
        result, _ = await delegate.handle_task(
            "flowscript.tensions", {"ir": envelope}, "t-nested-env"
        )
        assert result["metadata"]["total_tensions"] == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestDelegateErrors:
    """Test error cases."""

    @pytest.mark.asyncio
    async def test_unknown_skill(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        with pytest.raises(ValueError, match="Unknown skill"):
            await delegate.handle_task(
                "nonexistent.skill", _structured_input(simple_ir), "t-err"
            )

    @pytest.mark.asyncio
    async def test_why_missing_node_id(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        with pytest.raises(ValueError, match="node_id"):
            await delegate.handle_task(
                "flowscript.why", _structured_input(simple_ir), "t-err"
            )

    @pytest.mark.asyncio
    async def test_what_if_missing_node_id(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        with pytest.raises(ValueError, match="node_id"):
            await delegate.handle_task(
                "flowscript.what_if", _structured_input(simple_ir), "t-err"
            )

    @pytest.mark.asyncio
    async def test_alternatives_missing_question_id(self, simple_ir):
        delegate = FlowScriptMode3Delegate()
        with pytest.raises(ValueError, match="question_id"):
            await delegate.handle_task(
                "flowscript.alternatives",
                _structured_input(simple_ir),
                "t-err",
            )

    @pytest.mark.asyncio
    async def test_invalid_input_data(self):
        delegate = FlowScriptMode3Delegate()
        with pytest.raises(ValueError, match="Cannot extract IR"):
            await delegate.handle_task(
                "flowscript.tensions", {"garbage": True}, "t-err"
            )

    @pytest.mark.asyncio
    async def test_non_dict_input_data(self):
        delegate = FlowScriptMode3Delegate()
        with pytest.raises(ValueError, match="must be a dict"):
            await delegate.handle_task(
                "flowscript.tensions", "not a dict", "t-err"
            )


# ---------------------------------------------------------------------------
# Identity and capabilities
# ---------------------------------------------------------------------------


class TestDelegateIdentity:
    """Test identity card construction and capabilities."""

    def test_default_identity(self):
        delegate = FlowScriptMode3Delegate()
        identity = delegate.identity
        assert identity.delegate_id == "flowscript-ldp:mode3"
        assert identity.name == "FlowScript Mode 3"
        assert identity.model_family == "flowscript"

    def test_mode3_in_supported_modes(self):
        delegate = FlowScriptMode3Delegate()
        modes = delegate.identity.supported_payload_modes
        assert PayloadMode.SEMANTIC_GRAPH in modes
        assert PayloadMode.SEMANTIC_FRAME in modes
        assert PayloadMode.TEXT in modes

    def test_all_skills_advertised(self):
        delegate = FlowScriptMode3Delegate()
        cap_names = {c.name for c in delegate.identity.capabilities}
        for skill_name in SKILLS:
            assert skill_name in cap_names, f"Skill {skill_name} not in capabilities"

    def test_quality_metrics(self):
        delegate = FlowScriptMode3Delegate()
        for cap in delegate.identity.capabilities:
            assert cap.quality is not None
            assert cap.quality.quality_score == 1.0
            assert cap.quality.cost_per_call_usd == 0.0
            assert cap.quality.latency_p50_ms == 1

    def test_custom_delegate_id(self):
        delegate = FlowScriptMode3Delegate(
            delegate_id="custom:delegate:1",
            name="Custom Delegate",
        )
        assert delegate.identity.delegate_id == "custom:delegate:1"
        assert delegate.identity.name == "Custom Delegate"
        # Other defaults still apply
        assert delegate.identity.model_family == "flowscript"

    def test_cross_domain_trust(self):
        delegate = FlowScriptMode3Delegate()
        assert delegate.identity.trust_domain.allow_cross_domain is True


# ---------------------------------------------------------------------------
# Session negotiation (Mode 3 bypass)
# ---------------------------------------------------------------------------


class TestDelegateNegotiation:
    """Test that Mode 3 is correctly negotiated despite SDK's is_implemented gate."""

    def test_mode3_negotiated_when_both_support(self):
        delegate = FlowScriptMode3Delegate()
        # Simulate SESSION_PROPOSE with Mode 3 preference
        propose = LdpEnvelope.create(
            session_id="",
            from_id="test:client:1",
            to_id="flowscript-ldp:mode3",
            body=LdpMessageBody.session_propose(
                config={
                    "preferred_payload_modes": [
                        PayloadMode.SEMANTIC_GRAPH.value,
                        PayloadMode.SEMANTIC_FRAME.value,
                        PayloadMode.TEXT.value,
                    ],
                }
            ),
        )
        response = delegate._handle_session_propose(propose)
        assert response.body.negotiated_mode == PayloadMode.SEMANTIC_GRAPH

    def test_falls_back_to_semantic_frame(self):
        delegate = FlowScriptMode3Delegate()
        # Client only supports Mode 1 and 0
        propose = LdpEnvelope.create(
            session_id="",
            from_id="test:client:2",
            to_id="flowscript-ldp:mode3",
            body=LdpMessageBody.session_propose(
                config={
                    "preferred_payload_modes": [
                        PayloadMode.SEMANTIC_FRAME.value,
                        PayloadMode.TEXT.value,
                    ],
                }
            ),
        )
        response = delegate._handle_session_propose(propose)
        assert response.body.negotiated_mode == PayloadMode.SEMANTIC_FRAME

    def test_falls_back_to_text(self):
        delegate = FlowScriptMode3Delegate()
        # Client only supports text
        propose = LdpEnvelope.create(
            session_id="",
            from_id="test:client:3",
            to_id="flowscript-ldp:mode3",
            body=LdpMessageBody.session_propose(
                config={
                    "preferred_payload_modes": [
                        PayloadMode.TEXT.value,
                    ],
                }
            ),
        )
        response = delegate._handle_session_propose(propose)
        assert response.body.negotiated_mode == PayloadMode.TEXT

    def test_no_config_defaults_to_text(self):
        delegate = FlowScriptMode3Delegate()
        propose = LdpEnvelope.create(
            session_id="",
            from_id="test:client:4",
            to_id="flowscript-ldp:mode3",
            body=LdpMessageBody.session_propose(config={}),
        )
        response = delegate._handle_session_propose(propose)
        assert response.body.negotiated_mode == PayloadMode.TEXT

    def test_response_has_session_id(self):
        delegate = FlowScriptMode3Delegate()
        propose = LdpEnvelope.create(
            session_id="",
            from_id="test:client:5",
            to_id="flowscript-ldp:mode3",
            body=LdpMessageBody.session_propose(
                config={
                    "preferred_payload_modes": [PayloadMode.SEMANTIC_GRAPH.value],
                }
            ),
        )
        response = delegate._handle_session_propose(propose)
        assert response.body.session_id  # non-empty
        assert response.body.type == "SESSION_ACCEPT"

    def test_unknown_mode_values_skipped(self):
        """Unknown/future mode values should be skipped, not crash."""
        delegate = FlowScriptMode3Delegate()
        propose = LdpEnvelope.create(
            session_id="",
            from_id="test:client:6",
            to_id="flowscript-ldp:mode3",
            body=LdpMessageBody.session_propose(
                config={
                    "preferred_payload_modes": [
                        "future_mode_99",
                        PayloadMode.SEMANTIC_FRAME.value,
                    ],
                }
            ),
        )
        response = delegate._handle_session_propose(propose)
        # Should skip the unknown mode and negotiate SEMANTIC_FRAME
        assert response.body.negotiated_mode == PayloadMode.SEMANTIC_FRAME

    def test_all_unknown_modes_falls_to_text(self):
        """If all proposed modes are unknown, fall back to TEXT."""
        delegate = FlowScriptMode3Delegate()
        propose = LdpEnvelope.create(
            session_id="",
            from_id="test:client:7",
            to_id="flowscript-ldp:mode3",
            body=LdpMessageBody.session_propose(
                config={
                    "preferred_payload_modes": ["bogus_mode_1", "bogus_mode_2"],
                }
            ),
        )
        response = delegate._handle_session_propose(propose)
        assert response.body.negotiated_mode == PayloadMode.TEXT

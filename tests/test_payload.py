"""Tests for Mode 3 payload encode/decode."""

import pytest

from flowscript_ldp.payload import FlowScriptPayload, Mode3Envelope


class TestPayloadEncode:
    def test_encode_produces_valid_envelope(self, simple_ir):
        payload = FlowScriptPayload(simple_ir)
        encoded = payload.encode()
        assert encoded["ldp_version"] == "1.0"
        assert encoded["payload_mode"] == 3
        assert encoded["payload_format"] == "flowscript-ir"
        assert "ir" in encoded
        assert "capabilities" in encoded
        assert "why" in encoded["capabilities"]

    def test_provenance_metadata(self, simple_ir):
        payload = FlowScriptPayload(simple_ir)
        encoded = payload.encode()
        prov = encoded["provenance"]
        assert prov["node_count"] == 2
        assert prov["relationship_count"] == 1
        assert prov["source_system"] == "flowscript-ldp"


class TestPayloadDecode:
    def test_round_trip(self, simple_ir):
        payload = FlowScriptPayload(simple_ir)
        encoded = payload.encode()
        decoded = FlowScriptPayload.decode(encoded)
        assert len(decoded.ir.nodes) == len(simple_ir.nodes)
        assert len(decoded.ir.relationships) == len(simple_ir.relationships)

    def test_reject_wrong_mode(self, simple_ir):
        payload = FlowScriptPayload(simple_ir)
        encoded = payload.encode()
        encoded["payload_mode"] = 1
        with pytest.raises(ValueError, match="Expected Mode 3"):
            FlowScriptPayload.decode(encoded)

    def test_reject_wrong_format(self, simple_ir):
        payload = FlowScriptPayload(simple_ir)
        encoded = payload.encode()
        encoded["payload_format"] = "other-format"
        with pytest.raises(ValueError, match="Expected flowscript-ir"):
            FlowScriptPayload.decode(encoded)


class TestPayloadQuery:
    def test_query_access(self, decision_ir):
        payload = FlowScriptPayload(decision_ir)
        tensions = payload.query.tensions()
        assert tensions.metadata["total_tensions"] == 1

    def test_decode_then_query(self, decision_ir):
        payload = FlowScriptPayload(decision_ir)
        encoded = payload.encode()
        decoded = FlowScriptPayload.decode(encoded)
        tensions = decoded.query.tensions()
        assert tensions.metadata["total_tensions"] == 1


class TestNegotiation:
    def test_capability_manifest(self, simple_ir):
        payload = FlowScriptPayload(simple_ir)
        manifest = payload.negotiate_capabilities()
        assert 3 in manifest["supported_modes"]
        assert manifest["preferred_mode"] == 3
        assert manifest["payload_format"] == "flowscript-ir"
        assert manifest["fallback_chain"] == [3, 1, 0]

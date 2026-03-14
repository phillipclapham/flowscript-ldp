"""
Mode 3 Payload: Encode/decode/envelope for LDP semantic graph payloads.

This is the integration point — FlowScript IR wrapped in LDP Mode 3 envelope
with capability advertisement and provenance metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from . import __version__
from .ir import IR
from .query import QueryEngine


class PayloadProvenance(BaseModel):
    """Provenance metadata for the payload itself."""

    created_at: str
    source_system: str = "flowscript-ldp"
    source_version: str = __version__
    ir_version: str = "1.0.0"
    node_count: int = 0
    relationship_count: int = 0
    state_count: int = 0


class Mode3Envelope(BaseModel):
    """LDP Mode 3 payload envelope.

    Wraps FlowScript IR in the LDP protocol format with capability
    advertisement and provenance metadata.
    """

    ldp_version: str = "1.0"
    payload_mode: int = 3
    payload_format: str = "flowscript-ir"
    payload_version: str = "1.0.0"
    ir: dict[str, Any]  # Serialized IR
    capabilities: list[str] = Field(
        default_factory=lambda: [
            "why",
            "whatIf",
            "tensions",
            "blocked",
            "alternatives",
        ]
    )
    provenance: PayloadProvenance


class FlowScriptPayload:
    """Mode 3 payload handler.

    Encodes FlowScript IR into LDP Mode 3 envelopes and decodes them back.
    Provides query access to the underlying graph.
    """

    def __init__(self, ir: IR):
        self._ir = ir
        self._query = QueryEngine(ir)

    @property
    def ir(self) -> IR:
        return self._ir

    @property
    def query(self) -> QueryEngine:
        return self._query

    def encode(self) -> dict[str, Any]:
        """Encode IR into Mode 3 payload envelope."""
        ir_dict = self._ir.model_dump(mode="json")
        envelope = Mode3Envelope(
            ir=ir_dict,
            provenance=PayloadProvenance(
                created_at=datetime.now(tz=timezone.utc).isoformat(),
                node_count=len(self._ir.nodes),
                relationship_count=len(self._ir.relationships),
                state_count=len(self._ir.states),
            ),
        )
        return envelope.model_dump(mode="json")

    @classmethod
    def decode(cls, data: dict[str, Any]) -> FlowScriptPayload:
        """Decode Mode 3 payload envelope back to FlowScriptPayload.

        Validates envelope structure and reconstructs typed IR.
        """
        envelope = Mode3Envelope.model_validate(data)

        if envelope.payload_mode != 3:
            raise ValueError(
                f"Expected Mode 3 payload, got Mode {envelope.payload_mode}"
            )

        if envelope.payload_format != "flowscript-ir":
            raise ValueError(
                f"Expected flowscript-ir format, got {envelope.payload_format}"
            )

        ir = IR.model_validate(envelope.ir)
        return cls(ir)

    @classmethod
    def from_ir(cls, ir: IR) -> FlowScriptPayload:
        """Create payload from an IR model."""
        return cls(ir)

    @classmethod
    def from_dict(cls, ir_data: dict[str, Any]) -> FlowScriptPayload:
        """Create payload from raw IR dictionary."""
        ir = IR.model_validate(ir_data)
        return cls(ir)

    def negotiate_capabilities(self) -> dict[str, Any]:
        """Generate capability manifest for LDP session establishment.

        Used during SESSION_PROPOSE to advertise Mode 3 support.
        """
        return {
            "supported_modes": [0, 1, 3],  # Text, Semantic Frames, Semantic Graphs
            "preferred_mode": 3,
            "payload_format": "flowscript-ir",
            "capabilities": [
                "why",
                "whatIf",
                "tensions",
                "blocked",
                "alternatives",
            ],
            "ir_version": "1.0.0",
            "fallback_chain": [3, 1, 0],
        }

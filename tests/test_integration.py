"""
Integration smoke test: full network round-trip.

Starts FlowScriptMode3Delegate as an HTTP server, then uses
FlowScriptLdpAdapter (via LdpClient) to discover, establish session,
and submit Mode 3 tasks over the wire.

This is the real thing — actual HTTP, actual protocol negotiation,
actual query results.
"""

import asyncio
import multiprocessing
import time

import pytest

ldp_protocol = pytest.importorskip("ldp_protocol")
jamjet = pytest.importorskip("jamjet")

try:
    import uvicorn  # noqa: F401
    import starlette  # noqa: F401
    HAS_SERVER = True
except ImportError:
    HAS_SERVER = False

from ldp_protocol import LdpClient, PayloadMode

from flowscript_ldp.delegate import FlowScriptMode3Delegate
from flowscript_ldp.adapter import FlowScriptLdpAdapter
from flowscript_ldp.ir import (
    IR, Node, NodeType, Relationship, RelationType,
    State, StateType, StateFields, Provenance, GraphInvariants,
)


# ---------------------------------------------------------------------------
# Test IR fixture (inline — don't depend on conftest for integration tests)
# ---------------------------------------------------------------------------

def _build_test_ir() -> dict:
    """Build a test IR with enough structure to exercise all queries."""
    prov = Provenance(source_file="integration.fs", line_number=1, timestamp="2026-03-14T20:00:00Z")
    q_id = "q" * 64
    alt1_id = "a" * 64
    alt2_id = "b" * 64
    stmt1_id = "s" * 64
    stmt2_id = "t" * 64
    blocker_id = "x" * 64

    ir = IR(
        version="1.0.0",
        nodes=[
            Node(id=q_id, type=NodeType.QUESTION, content="Redis or PostgreSQL?", provenance=prov),
            Node(id=alt1_id, type=NodeType.ALTERNATIVE, content="PostgreSQL", provenance=prov),
            Node(id=alt2_id, type=NodeType.ALTERNATIVE, content="Redis", provenance=prov),
            Node(id=stmt1_id, type=NodeType.STATEMENT, content="ACID guarantees", provenance=prov),
            Node(id=stmt2_id, type=NodeType.STATEMENT, content="sub-ms reads", provenance=prov),
            Node(id=blocker_id, type=NodeType.BLOCKER, content="need benchmarks first", provenance=prov),
        ],
        relationships=[
            Relationship(id="r1" + "0" * 62, type=RelationType.ALTERNATIVE, source=q_id, target=alt1_id, provenance=prov),
            Relationship(id="r2" + "0" * 62, type=RelationType.ALTERNATIVE, source=q_id, target=alt2_id, provenance=prov),
            Relationship(id="r3" + "0" * 62, type=RelationType.CAUSES, source=alt1_id, target=stmt1_id, provenance=prov),
            Relationship(id="r4" + "0" * 62, type=RelationType.CAUSES, source=alt2_id, target=stmt2_id, provenance=prov),
            Relationship(
                id="r5" + "0" * 62, type=RelationType.TENSION,
                source=stmt1_id, target=stmt2_id,
                axis_label="consistency vs speed", provenance=prov,
            ),
            Relationship(id="r6" + "0" * 62, type=RelationType.CAUSES, source=blocker_id, target=q_id, provenance=prov),
        ],
        states=[
            State(
                id="st" + "0" * 62, type=StateType.DECIDED, node_id=alt1_id,
                fields=StateFields(rationale="need ACID", on="2026-03-14"), provenance=prov,
            ),
            State(
                id="sb" + "0" * 62, type=StateType.BLOCKED, node_id=blocker_id,
                fields=StateFields(reason="waiting on load tests", since="2026-03-10T00:00:00Z"), provenance=prov,
            ),
        ],
        invariants=GraphInvariants(),
    )
    return ir.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Server process
# ---------------------------------------------------------------------------

def _run_delegate_server(port: int):
    """Run the delegate server in a subprocess."""
    delegate = FlowScriptMode3Delegate()
    delegate.run(host="127.0.0.1", port=port)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_SERVER, reason="requires ldp-protocol[server]")
class TestIntegrationRoundTrip:
    """Full HTTP round-trip: delegate server + LdpClient + adapter."""

    PORT = 18090  # high port to avoid conflicts

    @pytest.fixture(autouse=True)
    def _server(self):
        """Start delegate server in a subprocess, wait for it, shut down after."""
        proc = multiprocessing.Process(
            target=_run_delegate_server,
            args=(self.PORT,),
            daemon=True,
        )
        proc.start()

        # Wait for server to be ready
        import httpx
        url = f"http://127.0.0.1:{self.PORT}/ldp/identity"
        for _ in range(30):
            try:
                resp = httpx.get(url, timeout=0.5)
                if resp.status_code == 200:
                    break
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            time.sleep(0.1)

        yield

        proc.terminate()
        proc.join(timeout=3)

    @pytest.mark.asyncio
    async def test_discover_delegate(self):
        """Discover the delegate's identity card over HTTP."""
        async with LdpClient() as client:
            identity = await client.discover(f"http://127.0.0.1:{self.PORT}")

        assert identity.name == "FlowScript Mode 3"
        assert identity.delegate_id == "flowscript-ldp:mode3"
        assert identity.model_family == "flowscript"

        # Verify all 6 skills advertised
        skill_names = {c.name for c in identity.capabilities}
        assert "flowscript.tensions" in skill_names
        assert "flowscript.blocked" in skill_names
        assert "flowscript.why" in skill_names
        assert "flowscript.what_if" in skill_names
        assert "flowscript.alternatives" in skill_names
        assert "flowscript.degrade" in skill_names

    @pytest.mark.asyncio
    async def test_establish_session(self):
        """Establish a session with Mode 3 negotiation."""
        async with LdpClient(
            config=ldp_protocol.SessionConfig(
                preferred_payload_modes=[
                    PayloadMode.SEMANTIC_GRAPH,
                    PayloadMode.SEMANTIC_FRAME,
                    PayloadMode.TEXT,
                ],
            )
        ) as client:
            session = await client.establish_session(f"http://127.0.0.1:{self.PORT}")

        assert session.state.value == "active"
        # Mode 3 should be negotiated (our delegate bypasses the SDK gate)
        assert session.payload.mode == PayloadMode.SEMANTIC_GRAPH

    @pytest.mark.asyncio
    async def test_submit_tensions_query(self):
        """Submit a tensions query over the wire and get real results."""
        ir_json = _build_test_ir()

        async with LdpClient() as client:
            result = await client.submit_task(
                f"http://127.0.0.1:{self.PORT}",
                skill="flowscript.tensions",
                input_data={"ir": ir_json},
            )

        output = result["output"]
        assert output["metadata"]["total_tensions"] == 1
        assert len(output["tensions"]) == 1
        assert output["tensions"][0]["axis"] == "consistency vs speed"

    @pytest.mark.asyncio
    async def test_submit_blocked_query(self):
        """Submit a blocked query and verify impact analysis."""
        ir_json = _build_test_ir()

        async with LdpClient() as client:
            result = await client.submit_task(
                f"http://127.0.0.1:{self.PORT}",
                skill="flowscript.blocked",
                input_data={"ir": ir_json},
            )

        output = result["output"]
        assert len(output["blockers"]) == 1
        assert output["blockers"][0]["reason"] == "waiting on load tests"

    @pytest.mark.asyncio
    async def test_submit_why_query(self):
        """Submit a causal ancestry query."""
        ir_json = _build_test_ir()
        stmt1_id = "s" * 64  # "ACID guarantees" node

        async with LdpClient() as client:
            result = await client.submit_task(
                f"http://127.0.0.1:{self.PORT}",
                skill="flowscript.why",
                input_data={"ir": ir_json, "node_id": stmt1_id},
            )

        output = result["output"]
        assert output["root_cause"] == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_submit_alternatives_query(self):
        """Submit a decision reconstruction query."""
        ir_json = _build_test_ir()
        q_id = "q" * 64

        async with LdpClient() as client:
            result = await client.submit_task(
                f"http://127.0.0.1:{self.PORT}",
                skill="flowscript.alternatives",
                input_data={"ir": ir_json, "question_id": q_id},
            )

        output = result["output"]
        assert len(output["options_considered"]) == 2
        assert output["chosen"] == "PostgreSQL"

    @pytest.mark.asyncio
    async def test_submit_degrade_to_mode1(self):
        """Submit a degradation request and get Mode 1 semantic frame."""
        ir_json = _build_test_ir()

        async with LdpClient() as client:
            result = await client.submit_task(
                f"http://127.0.0.1:{self.PORT}",
                skill="flowscript.degrade",
                input_data={"ir": ir_json, "target_mode": 1},
            )

        output = result["output"]
        assert output["target_mode"] == 1
        assert "task_type" in output["degraded"]

    @pytest.mark.asyncio
    async def test_submit_degrade_to_mode0(self):
        """Submit a degradation request and get Mode 0 prose."""
        ir_json = _build_test_ir()

        async with LdpClient() as client:
            result = await client.submit_task(
                f"http://127.0.0.1:{self.PORT}",
                skill="flowscript.degrade",
                input_data={"ir": ir_json, "target_mode": 0},
            )

        output = result["output"]
        assert output["target_mode"] == 0
        assert isinstance(output["degraded"], str)
        assert len(output["degraded"]) > 0

    @pytest.mark.asyncio
    async def test_provenance_in_result(self):
        """Verify results carry provenance metadata."""
        ir_json = _build_test_ir()

        async with LdpClient() as client:
            result = await client.submit_task(
                f"http://127.0.0.1:{self.PORT}",
                skill="flowscript.tensions",
                input_data={"ir": ir_json},
            )

        assert result["provenance"] is not None
        assert result["provenance"]["produced_by"] == "flowscript-ldp:mode3"

    @pytest.mark.asyncio
    async def test_adapter_discover_over_http(self):
        """FlowScriptLdpAdapter discovers the delegate via HTTP."""
        adapter = FlowScriptLdpAdapter()
        caps = await adapter.discover(f"http://127.0.0.1:{self.PORT}")

        assert caps.name == "FlowScript Mode 3"
        assert len(caps.skills) == 6
        assert "ldp" in caps.protocols

        # Clean up the adapter's HTTP client
        await adapter._client.close()

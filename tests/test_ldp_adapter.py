"""Tests for FlowScriptLdpAdapter (JamJet ProtocolAdapter, client-side)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

jamjet = pytest.importorskip("jamjet")
ldp_protocol = pytest.importorskip("ldp_protocol")

from jamjet.protocols.adapter import (
    ProtocolAdapter,
    RemoteCapabilities,
    TaskRequest,
    TaskStatus,
)
from jamjet.protocols.registry import get_registry, ProtocolRegistry
from ldp_protocol import LdpCapability, LdpIdentityCard, QualityMetrics, TrustDomain

from flowscript_ldp.adapter import FlowScriptLdpAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset the default ProtocolRegistry after each test."""
    registry = get_registry()
    yield
    # Remove any adapters registered during the test
    registry._adapters.clear()
    registry._url_prefixes.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_identity() -> LdpIdentityCard:
    """Build a mock LdpIdentityCard for testing."""
    return LdpIdentityCard(
        delegate_id="test:delegate:1",
        name="Test Delegate",
        description="A test delegate",
        model_family="test",
        model_version="1.0",
        context_window=128000,
        trust_domain=TrustDomain(name="test"),
        capabilities=[
            LdpCapability(
                name="flowscript.tensions",
                description="Analyze tradeoffs",
                quality=QualityMetrics(quality_score=1.0),
            ),
            LdpCapability(
                name="flowscript.blocked",
                description="Find blockers",
                quality=QualityMetrics(quality_score=1.0),
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Type and construction
# ---------------------------------------------------------------------------


class TestLdpAdapterConstruction:
    """Test adapter creation and type hierarchy."""

    def test_is_protocol_adapter_subclass(self):
        adapter = FlowScriptLdpAdapter()
        assert isinstance(adapter, ProtocolAdapter)

    def test_has_result_cache(self):
        adapter = FlowScriptLdpAdapter()
        assert adapter._results == {}

    def test_has_ldp_client(self):
        adapter = FlowScriptLdpAdapter()
        assert adapter._client is not None


# ---------------------------------------------------------------------------
# discover()
# ---------------------------------------------------------------------------


class TestLdpAdapterDiscover:
    """Test discover() maps LDP identity to JamJet RemoteCapabilities."""

    @pytest.mark.asyncio
    async def test_discover_returns_remote_capabilities(self):
        adapter = FlowScriptLdpAdapter()
        mock_identity = _mock_identity()

        with patch.object(adapter._client, "discover", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = mock_identity
            caps = await adapter.discover("http://localhost:8090")

        assert isinstance(caps, RemoteCapabilities)
        assert caps.name == "Test Delegate"
        assert caps.description == "A test delegate"
        assert len(caps.skills) == 2
        assert caps.skills[0].name == "flowscript.tensions"
        assert caps.skills[1].name == "flowscript.blocked"
        assert "ldp" in caps.protocols

    @pytest.mark.asyncio
    async def test_discover_maps_skill_schemas(self):
        adapter = FlowScriptLdpAdapter()
        identity = _mock_identity()
        identity.capabilities[0].input_schema = {"type": "object"}
        identity.capabilities[0].output_schema = {"type": "object"}

        with patch.object(adapter._client, "discover", new_callable=AsyncMock) as mock_discover:
            mock_discover.return_value = identity
            caps = await adapter.discover("http://localhost:8090")

        assert caps.skills[0].input_schema == {"type": "object"}
        assert caps.skills[0].output_schema == {"type": "object"}


# ---------------------------------------------------------------------------
# invoke()
# ---------------------------------------------------------------------------


class TestLdpAdapterInvoke:
    """Test invoke() submits tasks and caches results."""

    @pytest.mark.asyncio
    async def test_invoke_returns_task_handle(self):
        adapter = FlowScriptLdpAdapter()
        task = TaskRequest(skill="flowscript.tensions", input={"ir": {}})

        with patch.object(adapter._client, "submit_task", new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = {
                "task_id": "task-123",
                "output": {"tensions": []},
            }
            handle = await adapter.invoke("http://localhost:8090", task)

        assert handle.task_id == "task-123"
        assert handle.remote_url == "http://localhost:8090"

    @pytest.mark.asyncio
    async def test_invoke_caches_result(self):
        adapter = FlowScriptLdpAdapter()
        task = TaskRequest(skill="flowscript.tensions", input={"ir": {}})

        with patch.object(adapter._client, "submit_task", new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = {
                "task_id": "task-456",
                "output": {"tensions": [], "metadata": {}},
            }
            await adapter.invoke("http://localhost:8090", task)

        assert "task-456" in adapter._results
        assert adapter._results["task-456"]["output"] == {"tensions": [], "metadata": {}}

    @pytest.mark.asyncio
    async def test_invoke_passes_dict_input(self):
        adapter = FlowScriptLdpAdapter()
        input_data = {"ir": {"version": "1.0.0", "nodes": []}}
        task = TaskRequest(skill="flowscript.tensions", input=input_data)

        with patch.object(adapter._client, "submit_task", new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = {"task_id": "t", "output": {}}
            await adapter.invoke("http://localhost:8090", task)

            # Verify the input was passed as-is (not wrapped)
            call_kwargs = mock_submit.call_args
            assert call_kwargs.kwargs["input_data"] == input_data

    @pytest.mark.asyncio
    async def test_invoke_wraps_non_dict_input(self):
        adapter = FlowScriptLdpAdapter()
        task = TaskRequest(skill="flowscript.tensions", input="raw text")

        with patch.object(adapter._client, "submit_task", new_callable=AsyncMock) as mock_submit:
            mock_submit.return_value = {"task_id": "t", "output": {}}
            await adapter.invoke("http://localhost:8090", task)

            call_kwargs = mock_submit.call_args
            assert call_kwargs.kwargs["input_data"] == {"text": "raw text"}


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------


class TestLdpAdapterStatus:
    """Test status() returns cached results."""

    @pytest.mark.asyncio
    async def test_status_returns_completed_with_cached_result(self):
        adapter = FlowScriptLdpAdapter()
        adapter._results["task-789"] = {
            "task_id": "task-789",
            "output": {"tensions": [{"axis": "speed vs safety"}]},
        }

        status = await adapter.status("http://localhost:8090", "task-789")
        assert status.status == "completed"
        assert status.output == {"tensions": [{"axis": "speed vs safety"}]}

    @pytest.mark.asyncio
    async def test_status_returns_submitted_when_not_cached(self):
        adapter = FlowScriptLdpAdapter()
        status = await adapter.status("http://localhost:8090", "nonexistent")
        assert status.status == "submitted"


# ---------------------------------------------------------------------------
# stream()
# ---------------------------------------------------------------------------


class TestLdpAdapterStream:
    """Test stream() raises NotImplementedError."""

    @pytest.mark.asyncio
    async def test_stream_not_implemented(self):
        adapter = FlowScriptLdpAdapter()
        task = TaskRequest(skill="flowscript.tensions", input={})

        with pytest.raises(NotImplementedError, match="LDP streaming"):
            async for _ in adapter.stream("http://localhost:8090", task):
                pass


# ---------------------------------------------------------------------------
# cancel()
# ---------------------------------------------------------------------------


class TestLdpAdapterCacheEviction:
    """Test bounded result cache."""

    @pytest.mark.asyncio
    async def test_cache_evicts_oldest_when_full(self):
        adapter = FlowScriptLdpAdapter()
        adapter._max_cached = 3

        # Fill cache
        for i in range(3):
            adapter._results[f"task-{i}"] = {"output": f"result-{i}"}

        task = TaskRequest(skill="test", input={})
        with patch.object(adapter._client, "submit_task", new_callable=AsyncMock) as mock:
            mock.return_value = {"task_id": "task-new", "output": "new"}
            await adapter.invoke("http://localhost:8090", task)

        # Oldest (task-0) should be evicted
        assert "task-0" not in adapter._results
        assert "task-new" in adapter._results
        assert len(adapter._results) == 3


class TestLdpAdapterCancel:
    """Test cancel() cleans up cached results."""

    @pytest.mark.asyncio
    async def test_cancel_removes_cached_result(self):
        adapter = FlowScriptLdpAdapter()
        adapter._results["task-to-cancel"] = {"output": "something"}

        await adapter.cancel("http://localhost:8090", "task-to-cancel")
        assert "task-to-cancel" not in adapter._results

    @pytest.mark.asyncio
    async def test_cancel_noop_for_unknown_task(self):
        adapter = FlowScriptLdpAdapter()
        # Should not raise
        await adapter.cancel("http://localhost:8090", "nonexistent")


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------


class TestLdpAdapterRegistration:
    """Test registration with JamJet's ProtocolRegistry."""

    def test_register_adds_to_registry(self):
        # Use a fresh registry to avoid cross-test pollution
        FlowScriptLdpAdapter.register()
        registry = get_registry()

        adapter = registry.adapter("ldp")
        assert adapter is not None
        assert isinstance(adapter, FlowScriptLdpAdapter)

    def test_url_prefix_dispatch(self):
        FlowScriptLdpAdapter.register()
        registry = get_registry()

        assert registry.adapter_for_url("ldp://example.com") is not None
        assert registry.adapter_for_url("ldp+flowscript://example.com") is not None
        assert registry.adapter_for_url("http://example.com") is None

    def test_registered_as_protocol_adapter(self):
        FlowScriptLdpAdapter.register()
        registry = get_registry()

        adapter = registry.adapter("ldp")
        assert isinstance(adapter, ProtocolAdapter)

import asyncio
import json
import sys
from decimal import Decimal

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from agent_demo import mcp_server


class FakeEmbedder:
    def embed(self, texts):
        assert texts == ["退货政策"]
        return [[0.1] * 1024]


class FakeConn:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        if self.row is not None and "COUNT(*)" in str(statement):
            return FakeResult(self.row)
        return FakeRows()


class FakeRows:
    def all(self):
        return []


class FakeResult:
    def __init__(self, row):
        self.row = row

    def one(self):
        return self.row


class FakeContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *args):
        return False


class FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return FakeContext(self.conn)

    def begin(self):
        return FakeContext(self.conn)


def test_three_tools_are_registered() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {"search_knowledge", "summarize_sales", "remember_preference"} <= names


def test_stdio_transport_for_function_ai(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp_server.mcp, "run", lambda transport: calls.append(transport))
    monkeypatch.setattr(sys, "argv", ["tidb-agent-mcp", "--transport", "stdio"])
    mcp_server.main()
    assert calls == ["stdio"]


def test_search_uses_server_tenant_and_returns_json(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_TENANT_ID", "demo")
    conn = FakeConn()
    monkeypatch.setattr(mcp_server, "get_engine", lambda: FakeEngine(conn))
    monkeypatch.setattr(mcp_server, "get_embedder", lambda: FakeEmbedder())
    payload = json.loads(mcp_server.search_knowledge("退货政策", 2))
    assert payload == {"results": []}
    assert conn.calls[0][1]["tenant_id"] == "demo"
    assert conn.calls[0][1]["limit"] == 2
    assert "tenant_id" not in mcp_server.search_knowledge.__doc__


def test_sales_uses_fixed_paid_aggregation(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_TENANT_ID", "demo")
    row = type("Row", (), {"_mapping": {"order_count": 2, "revenue": Decimal("21400.00")}})()
    conn = FakeConn(row)
    monkeypatch.setattr(mcp_server, "get_engine", lambda: FakeEngine(conn))
    result = mcp_server.summarize_sales_impl("华东", "2026-11-01", "2026-12-01")
    assert result["order_count"] == 2
    assert result["revenue"] == "21400.00"
    assert "status = 'paid'" in conn.calls[0][0]
    assert conn.calls[0][1]["start"] == "2026-11-01 00:00:00"
    assert conn.calls[0][1]["end"] == "2026-12-01 00:00:00"


def test_sales_rejects_invalid_interval(monkeypatch) -> None:
    with pytest.raises(ValueError, match="start 必须早于 end"):
        mcp_server.summarize_sales_impl("华东", "2026-12-01", "2026-11-01")


def test_memory_is_idempotent_and_tenant_bound(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_TENANT_ID", "demo")
    conn = FakeConn()
    monkeypatch.setattr(mcp_server, "get_engine", lambda: FakeEngine(conn))
    first = mcp_server.remember_preference_impl("user-1", "先展示收入")
    second = mcp_server.remember_preference_impl("user-1", "先展示收入")
    assert first == second
    assert first["status"] == "saved"
    assert first["memory_id"].startswith("mem-")
    assert conn.calls[0][1]["tenant_id"] == "demo"
    assert "ON DUPLICATE KEY UPDATE" in conn.calls[0][0]


def test_tool_inputs_reject_blank_values() -> None:
    with pytest.raises(ValueError, match="query 不能为空"):
        mcp_server.search_knowledge_impl(" ")
    with pytest.raises(ValueError, match="preference 不能为空"):
        mcp_server.remember_preference_impl("user-1", " ")


def test_real_mcp_protocol_calls_with_fake_backends(monkeypatch) -> None:
    """Exercise initialize/list/call over MCP without any cloud connection."""
    monkeypatch.setenv("DEMO_TENANT_ID", "demo")
    row = type("Row", (), {"_mapping": {"order_count": 2, "revenue": Decimal("21400.00")}})()
    conn = FakeConn(row)
    monkeypatch.setattr(mcp_server, "get_engine", lambda: FakeEngine(conn))
    monkeypatch.setattr(mcp_server, "get_embedder", lambda: FakeEmbedder())

    async def exercise_protocol():
        async with create_connected_server_and_client_session(
            mcp_server.mcp, raise_exceptions=True
        ) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            search = await session.call_tool(
                "search_knowledge", {"query": "退货政策", "limit": 2}
            )
            sales = await session.call_tool(
                "summarize_sales",
                {"region": "华东", "start": "2026-11-01", "end": "2026-12-01"},
            )
            memory = await session.call_tool(
                "remember_preference",
                {"user_id": "user-1", "preference": "先展示收入"},
            )
            return initialized, tools, search, sales, memory

    initialized, tools, search, sales, memory = asyncio.run(exercise_protocol())
    assert initialized.serverInfo.name == "tidb-enterprise-agent"
    assert {tool.name for tool in tools.tools} == {
        "search_knowledge",
        "summarize_sales",
        "remember_preference",
    }
    assert not search.isError
    assert not sales.isError
    assert not memory.isError
    assert json.loads(search.content[0].text) == {"results": []}
    assert json.loads(sales.content[0].text)["revenue"] == "21400.00"
    assert json.loads(memory.content[0].text)["status"] == "saved"

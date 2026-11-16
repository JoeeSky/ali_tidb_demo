"""Local Streamable HTTP MCP server for the three scoped agent tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from sqlalchemy import text

from .db import create_tidb_engine
from .embeddings import BailianEmbedder
from .knowledge import search_documents


def _tenant_id() -> str:
    load_dotenv()
    tenant_id = os.environ.get("DEMO_TENANT_ID", "").strip()
    if not tenant_id:
        raise RuntimeError("缺少 DEMO_TENANT_ID；MCP 工具不接受模型指定租户")
    return tenant_id


def _required(value: str, field: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} 不能为空")
    if len(value) > max_length:
        raise ValueError(f"{field} 不能超过 {max_length} 个字符")
    return value


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


@lru_cache(maxsize=1)
def get_engine():
    """Create the small TiDB pool lazily, not at module import time."""
    return create_tidb_engine()


@lru_cache(maxsize=1)
def get_embedder() -> BailianEmbedder:
    return BailianEmbedder()


def search_knowledge_impl(query: str, limit: int = 5) -> list[dict[str, Any]]:
    query = _required(query, "query", 500)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError("limit 必须是 1～10 的整数")
    query_vector = get_embedder().embed([query])[0]
    with get_engine().connect() as conn:
        return search_documents(
            conn,
            tenant_id=_tenant_id(),
            query_vector=query_vector,
            limit=limit,
        )


def _parse_time(value: str, field: str) -> tuple[str, datetime]:
    value = _required(value, field, 32)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M:%S"), parsed
        except ValueError:
            continue
    raise ValueError(f"{field} 必须使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS 格式")


def summarize_sales_impl(region: str, start: str, end: str) -> dict[str, Any]:
    region = _required(region, "region", 32)
    start, start_dt = _parse_time(start, "start")
    end, end_dt = _parse_time(end, "end")
    if start_dt >= end_dt:
        raise ValueError("start 必须早于 end；统计区间为左闭右开 [start, end)")

    sql = text("""
        SELECT COUNT(*) AS order_count, COALESCE(SUM(amount), 0) AS revenue
        FROM sales_orders
        WHERE tenant_id = :tenant_id AND region = :region
          AND status = 'paid' AND ordered_at >= :start AND ordered_at < :end;
    """)
    with get_engine().connect() as conn:
        row = conn.execute(
            sql,
            {
                "tenant_id": _tenant_id(),
                "region": region,
                "start": start,
                "end": end,
            },
        ).one()
    revenue = row._mapping["revenue"]
    if isinstance(revenue, Decimal):
        revenue = format(revenue, ".2f")
    return {
        "region": region,
        "start": start,
        "end": end,
        "interval": "[start, end)",
        "status": "paid",
        "order_count": int(row._mapping["order_count"]),
        "revenue": revenue,
    }


def remember_preference_impl(user_id: str, preference: str) -> dict[str, str]:
    user_id = _required(user_id, "user_id", 64)
    preference = _required(preference, "preference", 1000)
    tenant_id = _tenant_id()
    digest = hashlib.sha256(f"{tenant_id}\0{user_id}\0{preference}".encode()).hexdigest()
    memory_id = f"mem-{digest[:24]}"
    sql = text("""
        INSERT INTO agent_memories (
          memory_id, tenant_id, user_id, memory_type, content, confidence
        ) VALUES (
          :memory_id, :tenant_id, :user_id, 'preference', :content, 1.00
        )
        ON DUPLICATE KEY UPDATE content = VALUES(content), confidence = 1.00;
    """)
    with get_engine().begin() as conn:
        conn.execute(
            sql,
            {
                "memory_id": memory_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "content": preference,
            },
        )
    return {
        "status": "saved",
        "memory_id": memory_id,
        "user_id": user_id,
        "preference": preference,
    }


load_dotenv()
mcp = FastMCP(
    "tidb-enterprise-agent",
    instructions=(
        "企业知识与经营分析工具。知识检索和销售汇总只读；"
        "remember_preference 只能在用户明确要求保存长期偏好时调用，不得保存密码、密钥或令牌。"
    ),
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8000")),
    json_response=True,
)


@mcp.tool()
def search_knowledge(query: str, limit: int = 5) -> str:
    """在企业知识库中检索相关资料；返回标题、来源、原文和距离，不修改数据。"""
    return _json({"results": search_knowledge_impl(query, limit)})


@mcp.tool()
def summarize_sales(region: str, start: str, end: str) -> str:
    """汇总指定区域和时间区间的已支付订单；区间左闭右开，只执行固定聚合 SQL。"""
    return _json(summarize_sales_impl(region, start, end))


@mcp.tool()
def remember_preference(user_id: str, preference: str) -> str:
    """仅在用户明确要求时保存一条非敏感长期偏好；不得用于密码、API Key 或令牌。"""
    return _json(remember_preference_impl(user_id, preference))


def main() -> None:
    """Run locally over HTTP or under Function AI's managed stdio adapter."""
    parser = argparse.ArgumentParser(description="TiDB enterprise agent MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default=os.environ.get("MCP_TRANSPORT", "streamable-http"),
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()

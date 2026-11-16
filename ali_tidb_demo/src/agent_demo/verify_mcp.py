"""Exercise the three tools through the real MCP Streamable HTTP protocol."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import timedelta
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

EXPECTED_TOOLS = {"search_knowledge", "summarize_sales", "remember_preference"}


def result_json(result: Any) -> Any:
    if result.isError:
        texts = [getattr(item, "text", str(item)) for item in result.content]
        raise RuntimeError("MCP 工具返回错误：" + "；".join(texts))
    texts = [item.text for item in result.content if getattr(item, "type", None) == "text"]
    if len(texts) != 1:
        raise RuntimeError("工具应返回一个 JSON 文本结果")
    return json.loads(texts[0])


async def verify(url: str) -> None:
    timeout = timedelta(seconds=120)
    async with httpx.AsyncClient(timeout=120) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read, write, _):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                print(f"[OK] MCP 初始化成功：{initialized.serverInfo.name}")

                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                missing = EXPECTED_TOOLS - names
                if missing:
                    raise RuntimeError(f"MCP 缺少工具：{sorted(missing)}")
                print(f"[OK] 工具列表：{', '.join(sorted(names))}")

                print("\n[1/3] search_knowledge")
                knowledge = result_json(await session.call_tool(
                    "search_knowledge",
                    {"query": "商品签收后多久可以申请无理由退货？", "limit": 3},
                    read_timeout_seconds=timeout,
                ))
                print(json.dumps(knowledge, ensure_ascii=False, indent=2))
                results = knowledge["results"]
                if not results or "7 个自然日" not in results[0]["content"]:
                    raise RuntimeError("知识检索未返回预期的 7 个自然日政策")
                print("[OK] 第一条资料包含预期政策，来源：" + results[0]["source_uri"])

                print("\n[2/3] summarize_sales")
                sales = result_json(await session.call_tool(
                    "summarize_sales",
                    {"region": "华东", "start": "2026-11-01", "end": "2026-12-01"},
                    read_timeout_seconds=timeout,
                ))
                print(json.dumps(sales, ensure_ascii=False, indent=2))
                if sales["order_count"] != 2 or str(sales["revenue"]) != "21400.00":
                    raise RuntimeError("销售汇总不等于预期的 2 笔、21400.00")
                print("[OK] 华东已支付订单：2 笔，收入 21400.00")

                print("\n[3/3] remember_preference（真实写入 TiDB）")
                memory = result_json(await session.call_tool(
                    "remember_preference",
                    {"user_id": "sa-demo-user", "preference": "先展示收入，再展示订单量。"},
                    read_timeout_seconds=timeout,
                ))
                print(json.dumps(memory, ensure_ascii=False, indent=2))
                if memory["status"] != "saved" or not memory["memory_id"].startswith("mem-"):
                    raise RuntimeError("长期偏好未返回预期的保存结果")
                print("[OK] 偏好已保存；请用后面的 SQL 独立核对 TiDB 行")


def main() -> int:
    parser = argparse.ArgumentParser(description="通过 MCP 协议验证三个本地工具")
    parser.add_argument("--execute", action="store_true", help="连接本地 MCP 和云端；第三项会写入一条偏好")
    args = parser.parse_args()
    load_dotenv()
    url = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
    print(f"MCP endpoint：{url}")
    if not args.execute:
        print("DRY-RUN：将依次验证 search_knowledge、summarize_sales、remember_preference")
        print("真实执行会连接百炼和 TiDB，并幂等写入 sa-demo-user 的一条演示偏好。")
        print("先启动 MCP 服务，再添加 --execute。")
        return 0
    asyncio.run(verify(url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

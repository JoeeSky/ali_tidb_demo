"""End-to-end RAG check: Bailian embedding -> TiDB retrieval -> Bailian answer."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from agent_demo.db import create_tidb_engine
from agent_demo.embeddings import BailianEmbedder
from agent_demo.generation import BailianGenerator
from agent_demo.knowledge import search_documents


def main() -> int:
    parser = argparse.ArgumentParser(description="基于 TiDB 检索资料生成有来源的回答")
    parser.add_argument("--query", default="签收后几天内可以申请无理由退货？")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--execute", action="store_true", help="确认后调用百炼并查询 TiDB")
    args = parser.parse_args()

    load_dotenv()
    tenant_id = os.environ.get("DEMO_TENANT_ID", "demo").strip()
    chat_model = os.environ.get("BAILIAN_CHAT_MODEL", "").strip()
    embedding_model = os.environ.get("EMBEDDING_MODEL", "").strip()
    if not chat_model or not embedding_model:
        raise RuntimeError("必须在 .env 显式配置 BAILIAN_CHAT_MODEL 和 EMBEDDING_MODEL")
    base_url = os.environ.get("BAILIAN_BASE_URL", "").strip()
    print(f"租户：{tenant_id}；问题：{args.query}")
    print(f"链路：{embedding_model} → TiDB Vector → {chat_model}")
    print(f"百炼 endpoint：{base_url or '未配置'}")
    if not args.execute:
        print("当前是 dry-run，没有调用百炼或连接 TiDB。添加 --execute 后才会执行。")
        return 0

    try:
        query_vector = BailianEmbedder().embed([args.query])[0]
        engine = create_tidb_engine()
        try:
            with engine.connect() as conn:
                rows = search_documents(
                    conn,
                    tenant_id=tenant_id,
                    query_vector=query_vector,
                    limit=args.limit,
                )
        finally:
            engine.dispose()

        print(f"[检索] TiDB 返回 {len(rows)} 个分块")
        for index, row in enumerate(rows, start=1):
            print(
                f"  资料{index}：{row['title']}；"
                f"距离={float(row['distance']):.6f}；来源={row['source_uri']}"
            )

        answer = BailianGenerator().generate(args.query, rows)
    except Exception as exc:
        print(f"[失败] {type(exc).__name__}: {exc}")
        print("请区分 Embedding、TiDB 检索和 Chat 模型错误；不要贴出密钥。")
        return 1

    print("\n--- 生成回答 ---")
    print(answer)
    print("\n--- 本次检索来源 ---")
    for index, row in enumerate(rows, start=1):
        print(f"资料{index}：{row['title']} | {row['source_uri']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

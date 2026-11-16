"""Run a real semantic query and an additional tenant-isolation check."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from agent_demo.db import create_tidb_engine
from agent_demo.embeddings import BailianEmbedder
from agent_demo.knowledge import search_documents

ISOLATION_TENANT = "sa-isolation-check"


def main() -> int:
    parser = argparse.ArgumentParser(description="检索 TiDB 中的演示知识")
    parser.add_argument("--query", default="签收后几天内可以申请无理由退货？")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--execute", action="store_true", help="确认后调用百炼并查询 TiDB")
    args = parser.parse_args()

    load_dotenv()
    tenant_id = os.environ.get("DEMO_TENANT_ID", "demo").strip()
    print(f"租户：{tenant_id}；问题：{args.query}；最多返回：{max(1, min(args.limit, 10))} 条")
    if not args.execute:
        print("当前是 dry-run，没有调用百炼或连接 TiDB。添加 --execute 后才会执行。")
        return 0

    embedder = BailianEmbedder()
    query_vector = embedder.embed([args.query])[0]
    engine = create_tidb_engine()
    try:
        with engine.connect() as conn:
            rows = search_documents(
                conn,
                tenant_id=tenant_id,
                query_vector=query_vector,
                limit=args.limit,
            )
            isolated_rows = search_documents(
                conn,
                tenant_id=ISOLATION_TENANT,
                query_vector=query_vector,
                limit=1,
            )
    finally:
        engine.dispose()

    print(f"[结果] 当前租户检索到 {len(rows)} 条")
    for rank, row in enumerate(rows, start=1):
        print(f"\n--- 结果 {rank} ---")
        print(f"标题：{row['title']}")
        print(f"来源：{row['source_uri']}")
        print(f"余弦距离：{float(row['distance']):.6f}")
        print(f"原文：{row['content']}")

    if isolated_rows:
        raise RuntimeError("租户隔离检查失败：检查租户检索到了其他数据")
    print("\n[OK] 租户隔离检查：检查租户返回 0 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

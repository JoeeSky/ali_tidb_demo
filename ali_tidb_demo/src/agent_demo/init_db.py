"""Initialize the demo schema. Cloud writes require an explicit --execute flag."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import text

from agent_demo.db import (
    configured_database,
    create_tidb_engine,
    quoted_database_name,
)

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"
EXPECTED_TABLES = {
    "sales_orders",
    "documents",
    "document_chunks",
    "conversations",
    "messages",
    "agent_memories",
    "agent_tasks",
    "agent_events",
}


def load_sql_statements(path: Path = SCHEMA_FILE) -> list[str]:
    """Split this repository's simple SQL file; no triggers or procedures are used."""
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    ]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化 TiDB Demo 数据表")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="确认后执行云端 CREATE DATABASE / CREATE TABLE；不加时仅显示计划",
    )
    args = parser.parse_args()

    database = configured_database()
    statements = load_sql_statements()
    print(f"目标数据库：{database}")
    print(f"待执行 DDL：{len(statements)} 条；预期数据表：{len(EXPECTED_TABLES)} 张")

    if not args.execute:
        print("当前是 dry-run，没有连接云端。审查 sql/schema.sql 后，添加 --execute 执行。")
        return 0

    server_engine = create_tidb_engine(with_database=False)
    try:
        with server_engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE DATABASE IF NOT EXISTS {quoted_database_name()}")
        print(f"[OK] 数据库已存在或已创建：{database}")
    finally:
        server_engine.dispose()

    engine = create_tidb_engine()
    try:
        with engine.begin() as conn:
            for index, statement in enumerate(statements, start=1):
                conn.exec_driver_sql(statement)
                print(f"[OK] DDL {index}/{len(statements)} 执行成功")

            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :database"
                ),
                {"database": database},
            ).scalars().all()
            missing = EXPECTED_TABLES.difference(rows)
            if missing:
                raise RuntimeError(f"建表后核对失败，缺少：{sorted(missing)}")
            print(f"[OK] 已核对 {len(EXPECTED_TABLES)} 张 Demo 数据表")
    finally:
        engine.dispose()

    print("初始化完成；尚未写入演示订单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

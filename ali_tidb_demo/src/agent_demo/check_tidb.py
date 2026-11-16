"""Read-only TiDB connectivity check; run this only after reviewing the code."""

from __future__ import annotations

from sqlalchemy import text

from agent_demo.db import configured_database, create_tidb_engine


def main() -> int:
    print("将使用 .env 中的凭证发起只读连接；不会输出用户名、密码或完整 DSN。")
    engine = create_tidb_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 AS ok, VERSION() AS version, DATABASE() AS database_name")
            ).one()
            if row.ok != 1:
                raise RuntimeError("SELECT 1 未返回预期结果")
            if row.database_name != configured_database():
                raise RuntimeError("连接后的数据库与配置不一致")

            print(f"[OK] SELECT 1 = {row.ok}")
            print(f"[OK] TiDB 版本：{row.version}")
            print(f"[OK] 当前数据库：{row.database_name}")

            ssl_row = conn.execute(text("SHOW STATUS LIKE 'Ssl_cipher'")).first()
            if ssl_row and ssl_row[1]:
                print("[OK] 当前连接已启用 TLS")
            else:
                print("[提醒] 未能读取 TLS cipher，请结合连接配置进一步确认")
    finally:
        engine.dispose()

    print("只读连接检查完成，没有创建或修改数据库对象。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

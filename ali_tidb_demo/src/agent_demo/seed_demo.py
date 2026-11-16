"""Insert a small, repeatable demo dataset after explicit user confirmation."""

from __future__ import annotations

import argparse
from decimal import Decimal

from sqlalchemy import text

from agent_demo.db import create_tidb_engine

DEMO_ORDERS = (
    ("o-001", "demo", "华东", Decimal("12800.00"), "paid", "2026-11-01 10:00:00"),
    ("o-002", "demo", "华东", Decimal("8600.00"), "paid", "2026-11-02 11:00:00"),
    ("o-003", "demo", "华南", Decimal("6900.00"), "paid", "2026-11-02 12:00:00"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="写入可重复执行的 Demo 订单")
    parser.add_argument("--execute", action="store_true", help="确认后写入云端数据")
    args = parser.parse_args()

    expected_revenue = sum((row[3] for row in DEMO_ORDERS if row[2] == "华东"), Decimal("0"))
    print(f"将写入或更新 {len(DEMO_ORDERS)} 笔订单；华东已支付订单预期合计：{expected_revenue}")
    if not args.execute:
        print("当前是 dry-run，没有连接云端。添加 --execute 才会写入。")
        return 0

    engine = create_tidb_engine()
    try:
        with engine.begin() as conn:
            for order in DEMO_ORDERS:
                conn.execute(
                    text(
                        "INSERT INTO sales_orders "
                        "(order_id, tenant_id, region, amount, status, ordered_at) "
                        "VALUES (:id, :tenant, :region, :amount, :status, :ordered_at) "
                        "ON DUPLICATE KEY UPDATE tenant_id = VALUES(tenant_id), "
                        "region = VALUES(region), amount = VALUES(amount), "
                        "status = VALUES(status), ordered_at = VALUES(ordered_at)"
                    ),
                    {
                        "id": order[0],
                        "tenant": order[1],
                        "region": order[2],
                        "amount": order[3],
                        "status": order[4],
                        "ordered_at": order[5],
                    },
                )

            result = conn.execute(
                text(
                    "SELECT COUNT(*) AS order_count, COALESCE(SUM(amount), 0) AS revenue "
                    "FROM sales_orders WHERE tenant_id = 'demo' AND region = '华东' "
                    "AND status = 'paid' AND ordered_at >= '2026-11-01 00:00:00' "
                    "AND ordered_at < '2026-12-01 00:00:00'"
                )
            ).one()

        if result.order_count != 2 or result.revenue != expected_revenue:
            raise RuntimeError(
                f"演示数据核对失败：预期 2 笔/{expected_revenue}，"
                f"实际 {result.order_count} 笔/{result.revenue}"
            )
        print(f"[OK] 华东订单核对：{result.order_count} 笔，销售额 {result.revenue}")
    finally:
        engine.dispose()

    print("演示数据写入完成；重复执行会更新相同 order_id，不会新增重复订单。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

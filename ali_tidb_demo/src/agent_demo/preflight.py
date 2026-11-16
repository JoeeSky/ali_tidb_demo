"""Validate local configuration without making network requests or printing secrets."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import load_dotenv

REQUIRED_SETTINGS = (
    "TIDB_DSN",
    "TIDB_DATABASE",
    "TIDB_SSL_CA",
    "DASHSCOPE_API_KEY",
    "BAILIAN_BASE_URL",
    "BAILIAN_CHAT_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
)


def validate_config(env: Mapping[str, str], *, require_agent: bool = False) -> list[str]:
    """Return actionable configuration errors; never include credential values."""
    errors: list[str] = []
    required = list(REQUIRED_SETTINGS)
    if require_agent:
        required.append("BAILIAN_APP_ID")

    for key in required:
        value = env.get(key, "").strip()
        if not value or value.startswith("<"):
            errors.append(f"缺少配置：{key}")

    dsn = env.get("TIDB_DSN", "").strip()
    if dsn and not dsn.startswith("<"):
        try:
            parsed = urlsplit(dsn)
            if parsed.scheme != "mysql+pymysql" or not parsed.hostname:
                errors.append("TIDB_DSN 必须是包含主机名的 mysql+pymysql:// 连接串")
            if not parsed.path.removeprefix("/"):
                errors.append("TIDB_DSN 必须包含数据库名，例如 /agent_demo")
        except ValueError:
            errors.append("TIDB_DSN 格式无效；请确认密码中的特殊字符已做 URL 编码")

    database = env.get("TIDB_DATABASE", "").strip()
    if database and not re.fullmatch(r"[A-Za-z0-9_]+", database):
        errors.append("TIDB_DATABASE 只能包含字母、数字和下划线")

    ca_path = env.get("TIDB_SSL_CA", "").strip()
    if ca_path and not ca_path.startswith("<") and not Path(ca_path).expanduser().is_file():
        errors.append("TIDB_SSL_CA 指向的 CA 文件不存在")

    base_url = env.get("BAILIAN_BASE_URL", "").strip()
    if base_url and not base_url.startswith("https://"):
        errors.append("BAILIAN_BASE_URL 必须使用 HTTPS")

    model = env.get("EMBEDDING_MODEL", "").strip()
    dimensions = env.get("EMBEDDING_DIMENSIONS", "").strip()
    if model and model != "text-embedding-v4":
        errors.append("基础版固定使用 text-embedding-v4；更换模型需同步迁移向量数据")
    if dimensions and dimensions != "1024":
        errors.append("基础版 EMBEDDING_DIMENSIONS 必须为 1024，与 VECTOR(1024) 一致")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Demo 本地配置，不连接云端")
    parser.add_argument("--agent", action="store_true", help="同时检查 BAILIAN_APP_ID")
    args = parser.parse_args()

    load_dotenv()
    print(f"[OK] Python {sys.version.split()[0]}")
    print("[OK] 已加载 .env（如存在）；本检查不会发起网络请求")

    errors = validate_config(os.environ, require_agent=args.agent)
    if errors:
        for error in errors:
            print(f"[待处理] {error}")
        print("\n请在项目目录的 .env 中补齐配置，然后重新运行预检。")
        return 2

    print("[OK] TiDB 与百炼基础配置完整，密钥内容未输出")
    print(f"[OK] 生成模型：{os.environ['BAILIAN_CHAT_MODEL']}")
    print(f"[OK] 向量模型与维度：{os.environ['EMBEDDING_MODEL']} / {os.environ['EMBEDDING_DIMENSIONS']}")
    if args.agent:
        print("[OK] 百炼 Agent App ID 已配置")
    print("下一步可以分别验证 Starter TLS 连接和百炼 API。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

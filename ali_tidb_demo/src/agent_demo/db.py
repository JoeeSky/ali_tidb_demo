"""TiDB connection helpers. No network connection is opened at import time."""

from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def tidb_url() -> URL:
    """Read the base DSN and apply a separate, explicit demo database target."""
    load_dotenv()
    dsn = os.environ.get("TIDB_DSN", "").strip()
    if not dsn:
        raise RuntimeError("缺少 TIDB_DSN，请检查项目目录中的 .env")
    database = os.environ.get("TIDB_DATABASE", "").strip()
    if not database:
        raise RuntimeError("缺少 TIDB_DATABASE；为防止误写已有数据库，必须显式配置目标库")
    return make_url(dsn).set(database=database)


def configured_database(url: URL | None = None) -> str:
    """Return and validate the configured database name."""
    database = (url or tidb_url()).database
    if not database:
        raise RuntimeError("必须配置目标数据库名，例如 TIDB_DATABASE=agent_demo")
    if not _IDENTIFIER.fullmatch(database):
        raise RuntimeError("数据库名只能包含字母、数字和下划线")
    return database


def quoted_database_name(url: URL | None = None) -> str:
    """Safely quote an already validated identifier for CREATE DATABASE."""
    return f"`{configured_database(url)}`"


def create_tidb_engine(*, with_database: bool = True) -> Engine:
    """Build a TLS-enabled SQLAlchemy engine with a deliberately small pool."""
    load_dotenv()
    url = tidb_url()
    if with_database:
        configured_database(url)
    else:
        url = url.set(database=None)

    ca_path = os.environ.get("TIDB_SSL_CA", "").strip()
    if not ca_path:
        raise RuntimeError("缺少 TIDB_SSL_CA")
    if not Path(ca_path).expanduser().is_file():
        raise RuntimeError("TIDB_SSL_CA 指向的 CA 文件不存在")

    return create_engine(
        url,
        connect_args={
            "ssl": {"ca": str(Path(ca_path).expanduser())},
            "connect_timeout": 10,
        },
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=240,
    )

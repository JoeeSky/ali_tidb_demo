import os

import pytest
from sqlalchemy.engine import make_url

from agent_demo.db import configured_database, quoted_database_name, tidb_url
from agent_demo.init_db import EXPECTED_TABLES, load_sql_statements


def test_configured_database_is_read_from_dsn() -> None:
    url = make_url("mysql+pymysql://user:secret@example.com:4000/demo")
    assert configured_database(url) == "demo"
    assert quoted_database_name(url) == "`demo`"


def test_target_database_is_separate_from_base_dsn(monkeypatch) -> None:
    monkeypatch.setenv(
        "TIDB_DSN", "mysql+pymysql://user:secret@example.com:4000/demo"
    )
    monkeypatch.setenv("TIDB_DATABASE", "agent_demo")
    url = tidb_url()
    assert url.database == "agent_demo"
    assert os.environ["TIDB_DSN"].endswith("/demo")


def test_target_database_must_be_explicit(monkeypatch) -> None:
    monkeypatch.setattr("agent_demo.db.load_dotenv", lambda: None)
    monkeypatch.setenv(
        "TIDB_DSN", "mysql+pymysql://user:secret@example.com:4000/demo"
    )
    monkeypatch.delenv("TIDB_DATABASE", raising=False)
    with pytest.raises(RuntimeError, match="防止误写"):
        tidb_url()


def test_database_name_is_required() -> None:
    url = make_url("mysql+pymysql://user:secret@example.com:4000/")
    with pytest.raises(RuntimeError, match="必须配置目标数据库名"):
        configured_database(url)


def test_database_identifier_rejects_sql_injection() -> None:
    url = make_url("mysql+pymysql://user:secret@example.com:4000/demo")
    url = url.set(database="demo`;DROP TABLE users;--")
    with pytest.raises(RuntimeError, match="只能包含"):
        configured_database(url)


def test_schema_contains_all_tables_and_matching_vector_dimension() -> None:
    statements = load_sql_statements()
    schema = "\n".join(statements)
    assert len(statements) == len(EXPECTED_TABLES) == 8
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
    assert "VECTOR(1024)" in schema
    assert "VEC_COSINE_DISTANCE" in schema


def test_schema_loader_ignores_comments_and_empty_statements() -> None:
    statements = load_sql_statements()
    assert all(statement for statement in statements)
    assert not any(statement.startswith("--") for statement in statements)

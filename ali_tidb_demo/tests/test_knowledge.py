from types import SimpleNamespace

import pytest

from agent_demo.knowledge import (
    chunk_id_for,
    chunk_text,
    content_sha256,
    document_id_for,
    search_documents,
)


def test_short_document_is_one_chunk() -> None:
    assert chunk_text("  短文档内容  ") == ["短文档内容"]


def test_long_document_has_bounded_chunks_and_overlap() -> None:
    content = "0123456789" * 30
    chunks = chunk_text(content, chunk_size=100, overlap=20)
    assert len(chunks) == 4
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert chunks[0][-20:] == chunks[1][:20]
    assert "".join(chunks).count("0123456789") >= 30


def test_invalid_chunk_parameters_fail() -> None:
    with pytest.raises(ValueError, match="分块参数"):
        chunk_text("内容", chunk_size=100, overlap=100)


def test_ids_are_deterministic_and_tenant_scoped() -> None:
    first = document_id_for("demo", "data/knowledge/a.md")
    assert first == document_id_for("demo", "data/knowledge/a.md")
    assert first != document_id_for("other", "data/knowledge/a.md")
    assert len(content_sha256("内容")) == 64
    assert chunk_id_for(first, 0, "内容").startswith("chunk-")


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeConnection:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        row = SimpleNamespace(
            _mapping={
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "title": "制度",
                "source_uri": "demo://policy",
                "content": "原文",
                "distance": 0.1,
            }
        )
        return FakeRows([row])


def test_search_uses_tenant_filter_and_vector_json() -> None:
    conn = FakeConnection()
    rows = search_documents(conn, tenant_id="demo", query_vector=[0.1] * 1024, limit=99)
    assert len(rows) == 1
    sql, parameters = conn.calls[0]
    assert "c.tenant_id = :tenant_id" in sql
    assert "d.tenant_id = c.tenant_id" in sql
    assert parameters["tenant_id"] == "demo"
    assert parameters["limit"] == 10
    assert parameters["query_vector"].startswith("[")


def test_search_rejects_wrong_dimension() -> None:
    with pytest.raises(ValueError, match="1024"):
        search_documents(FakeConnection(), tenant_id="demo", query_vector=[0.1] * 768)

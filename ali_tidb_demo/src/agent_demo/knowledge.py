"""Document chunking and tenant-scoped TiDB Vector search."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text


def chunk_text(content: str, *, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Chunk demo text by characters with a bounded overlap."""
    content = content.strip()
    if not content:
        raise ValueError("文档内容不能为空")
    if chunk_size < 50 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("分块参数必须满足 chunk_size >= 50 且 0 <= overlap < chunk_size")
    if len(content) <= chunk_size:
        return [content]

    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(start + chunk_size, len(content))
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(content):
            break
        start = end - overlap
    return chunks


def content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def document_id_for(tenant_id: str, relative_path: str) -> str:
    digest = hashlib.sha256(f"{tenant_id}:{relative_path}".encode("utf-8")).hexdigest()
    return f"doc-{digest[:24]}"


def chunk_id_for(document_id: str, chunk_no: int, content: str) -> str:
    digest = hashlib.sha256(f"{document_id}:{chunk_no}:{content}".encode("utf-8")).hexdigest()
    return f"chunk-{digest[:24]}"


def markdown_title(path: Path, content: str) -> str:
    first_line = content.lstrip().splitlines()[0]
    return first_line.removeprefix("#").strip() if first_line.startswith("#") else path.stem


def search_documents(
    conn: Any,
    *,
    tenant_id: str,
    query_vector: list[float],
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Run exact tenant pre-filtering; benchmark ANN behavior before production scale-up."""
    if not tenant_id.strip():
        raise ValueError("tenant_id 不能为空")
    if len(query_vector) != 1024:
        raise ValueError("查询向量必须为 1024 维")
    limit = max(1, min(limit, 10))
    rows = conn.execute(
        text(
            "SELECT c.chunk_id, c.document_id, d.title, d.source_uri, c.content, "
            "VEC_COSINE_DISTANCE(c.embedding, :query_vector) AS distance "
            "FROM document_chunks c "
            "JOIN documents d ON d.document_id = c.document_id "
            "AND d.tenant_id = c.tenant_id "
            "WHERE c.tenant_id = :tenant_id AND d.status = 'active' "
            "ORDER BY distance LIMIT :limit"
        ),
        {
            "tenant_id": tenant_id,
            "query_vector": json.dumps(query_vector, separators=(",", ":")),
            "limit": limit,
        },
    ).all()
    return [dict(row._mapping) for row in rows]

"""Ingest demo Markdown files into TiDB with repeatable, content-aware writes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from agent_demo.db import create_tidb_engine
from agent_demo.embeddings import BailianEmbedder
from agent_demo.knowledge import (
    chunk_id_for,
    chunk_text,
    content_sha256,
    document_id_for,
    markdown_title,
)

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge"


def main() -> int:
    parser = argparse.ArgumentParser(description="将演示文档分块、向量化并写入 TiDB")
    parser.add_argument("--execute", action="store_true", help="确认后调用百炼并写入 TiDB")
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    args = parser.parse_args()

    load_dotenv()
    tenant_id = os.environ.get("DEMO_TENANT_ID", "demo").strip()
    files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    if not files:
        raise RuntimeError(f"没有找到 Markdown 文档：{KNOWLEDGE_DIR}")

    prepared = []
    for path in files:
        content = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(KNOWLEDGE_DIR.parent.parent).as_posix()
        chunks = chunk_text(content, chunk_size=args.chunk_size, overlap=args.overlap)
        prepared.append((path, relative_path, content, chunks))
        print(f"待处理：{relative_path}，{len(chunks)} 个分块")

    print(f"租户：{tenant_id}；文档：{len(prepared)}；分块：{sum(len(item[3]) for item in prepared)}")
    if not args.execute:
        print("当前是 dry-run，没有调用百炼或连接 TiDB。添加 --execute 后才会执行。")
        return 0

    embedder = BailianEmbedder()
    engine = create_tidb_engine()
    try:
        for path, relative_path, content, chunks in prepared:
            document_id = document_id_for(tenant_id, relative_path)
            content_hash = content_sha256(content)
            title = markdown_title(path, content)
            source_uri = f"demo://{relative_path}"

            with engine.connect() as conn:
                existing = conn.execute(
                    text(
                        "SELECT content_hash FROM documents "
                        "WHERE tenant_id = :tenant_id AND document_id = :document_id"
                    ),
                    {"tenant_id": tenant_id, "document_id": document_id},
                ).first()
                chunk_count = conn.execute(
                    text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :document_id"),
                    {"document_id": document_id},
                ).scalar_one()

            if existing and existing.content_hash == content_hash and chunk_count == len(chunks):
                print(f"[跳过] 内容和分块未变化：{relative_path}")
                continue

            vectors = embedder.embed(chunks)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO documents "
                        "(document_id, tenant_id, title, source_uri, content_hash, status) "
                        "VALUES (:document_id, :tenant_id, :title, :source_uri, :content_hash, 'active') "
                        "ON DUPLICATE KEY UPDATE title = VALUES(title), "
                        "source_uri = VALUES(source_uri), content_hash = VALUES(content_hash), status = 'active'"
                    ),
                    {
                        "document_id": document_id,
                        "tenant_id": tenant_id,
                        "title": title,
                        "source_uri": source_uri,
                        "content_hash": content_hash,
                    },
                )
                conn.execute(
                    text("DELETE FROM document_chunks WHERE document_id = :document_id"),
                    {"document_id": document_id},
                )
                for chunk_no, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                    conn.execute(
                        text(
                            "INSERT INTO document_chunks "
                            "(chunk_id, document_id, tenant_id, chunk_no, content, embedding, embedding_model) "
                            "VALUES (:chunk_id, :document_id, :tenant_id, :chunk_no, :content, "
                            ":embedding, :embedding_model)"
                        ),
                        {
                            "chunk_id": chunk_id_for(document_id, chunk_no, chunk),
                            "document_id": document_id,
                            "tenant_id": tenant_id,
                            "chunk_no": chunk_no,
                            "content": chunk,
                            "embedding": json.dumps(vector, separators=(",", ":")),
                            "embedding_model": embedder.model,
                        },
                    )
            print(f"[OK] 已写入：{relative_path}，{len(chunks)} 个分块")

        with engine.connect() as conn:
            counts = conn.execute(
                text(
                    "SELECT (SELECT COUNT(*) FROM documents WHERE tenant_id = :tenant_id) AS documents, "
                    "(SELECT COUNT(*) FROM document_chunks WHERE tenant_id = :tenant_id) AS chunks"
                ),
                {"tenant_id": tenant_id},
            ).one()
        print(f"[OK] 当前租户知识库：{counts.documents} 篇文档，{counts.chunks} 个分块")
    finally:
        engine.dispose()

    print("知识导入完成。再次执行时，未变化的文档会跳过 Embedding 调用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

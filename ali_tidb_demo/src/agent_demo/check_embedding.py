"""Minimal real Bailian embedding request; requires explicit --execute."""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from agent_demo.embeddings import BailianEmbedder, cosine_similarity

SAMPLE_TEXTS = (
    "TiDB 是兼容 MySQL 协议的分布式数据库。",
    "TiDB 支持 MySQL 通信协议。",
    "今天适合去公园散步。",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="验证百炼 text-embedding-v4 最小调用")
    parser.add_argument("--execute", action="store_true", help="确认后发起一次真实 API 请求")
    args = parser.parse_args()

    load_dotenv()
    model = os.environ.get("EMBEDDING_MODEL", "").strip()
    dimensions = os.environ.get("EMBEDDING_DIMENSIONS", "").strip()
    if not model or not dimensions:
        raise RuntimeError("必须在 .env 显式配置 EMBEDDING_MODEL 和 EMBEDDING_DIMENSIONS")
    print(f"模型：{model}；显式维度：{dimensions}；输入：3 条文本，单次批量请求")
    if not args.execute:
        print("当前是 dry-run，没有连接百炼。添加 --execute 后才会发起请求。")
        return 0

    try:
        embedder = BailianEmbedder()
        vectors = embedder.embed(SAMPLE_TEXTS)
    except Exception as exc:
        print(f"[失败] {type(exc).__name__}: {exc}")
        print("请检查 API Key、base_url、业务空间、模型权限和网络；不要贴出密钥。")
        return 1

    print(f"[OK] 返回向量数量：{len(vectors)}")
    print(f"[OK] 向量维度：{sorted({len(vector) for vector in vectors})}")
    print(f"[观察] 两句 TiDB 文本相似度：{cosine_similarity(vectors[0], vectors[1]):.6f}")
    print(f"[观察] TiDB 与散步文本相似度：{cosine_similarity(vectors[0], vectors[2]):.6f}")
    print("相似度仅用于观察语义检索，不用任意固定阈值判定本次调用成败。")
    print("未输出 API Key、完整向量或业务空间标识。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

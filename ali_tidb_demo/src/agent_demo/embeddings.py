"""Alibaba Cloud Model Studio embeddings with strict shape validation."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


class BailianEmbedder:
    """Small OpenAI-compatible client fixed to the demo's vector contract."""

    def __init__(self, *, client: Any | None = None) -> None:
        load_dotenv()
        self.model = os.environ.get("EMBEDDING_MODEL", "").strip()
        dimensions_value = os.environ.get("EMBEDDING_DIMENSIONS", "").strip()
        if not self.model or not dimensions_value:
            raise RuntimeError("必须在 .env 显式配置 EMBEDDING_MODEL 和 EMBEDDING_DIMENSIONS")
        self.dimensions = int(dimensions_value)
        if self.model != "text-embedding-v4" or self.dimensions != 1024:
            raise RuntimeError("基础版要求 text-embedding-v4 和 1024 维，与 TiDB DDL 保持一致")

        if client is not None:
            self._client = client
            return

        base_url = os.environ.get("BAILIAN_BASE_URL", "").strip()
        if not base_url:
            raise RuntimeError("缺少 BAILIAN_BASE_URL；Embedding 不会默认回退到其他地域")

        headers = {}
        workspace_id = os.environ.get("BAILIAN_WORKSPACE_ID", "").strip()
        if workspace_id:
            headers["X-DashScope-WorkSpace"] = workspace_id
        self._client = OpenAI(
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url=base_url,
            default_headers=headers,
            timeout=30.0,
            max_retries=2,
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts in batches of at most 10 and validate every returned vector."""
        if not texts:
            return []
        if any(not isinstance(value, str) or not value.strip() for value in texts):
            raise ValueError("Embedding 输入必须是非空字符串，且不能包含空白文本")

        vectors: list[list[float]] = []
        for start in range(0, len(texts), 10):
            batch = list(texts[start : start + 10])
            response = self._client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
                encoding_format="float",
            )
            data = sorted(response.data, key=lambda item: item.index)
            if len(data) != len(batch):
                raise RuntimeError(
                    f"Embedding 返回条数不一致：输入 {len(batch)}，返回 {len(data)}"
                )
            for item in data:
                vector = list(item.embedding)
                if len(vector) != self.dimensions:
                    raise RuntimeError(
                        f"Embedding 维度不一致：期望 {self.dimensions}，实际 {len(vector)}"
                    )
                if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector):
                    raise RuntimeError("Embedding 返回了非数值或非有限值")
                vectors.append([float(value) for value in vector])
        return vectors


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Calculate cosine similarity without adding a numerical dependency."""
    if len(left) != len(right) or not left:
        raise ValueError("余弦相似度要求两个等长、非空向量")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("零向量不能计算余弦相似度")
    return dot / (left_norm * right_norm)

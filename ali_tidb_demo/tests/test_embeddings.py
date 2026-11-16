from types import SimpleNamespace

import pytest

from agent_demo.embeddings import BailianEmbedder, cosine_similarity


@pytest.fixture(autouse=True)
def embedding_environment(monkeypatch):
    monkeypatch.setattr("agent_demo.embeddings.load_dotenv", lambda: None)
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-v4")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "1024")


class FakeEmbeddings:
    def __init__(self, dimensions: int = 1024) -> None:
        self.dimensions = dimensions
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        batch = kwargs["input"]
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[0.5] * self.dimensions)
                for index in range(len(batch))
            ]
        )


class FakeClient:
    def __init__(self, dimensions: int = 1024) -> None:
        self.embeddings = FakeEmbeddings(dimensions)


def make_embedder(dimensions: int = 1024) -> tuple[BailianEmbedder, FakeClient]:
    client = FakeClient(dimensions)
    return BailianEmbedder(client=client), client


def test_embedding_batches_are_limited_to_ten() -> None:
    embedder, client = make_embedder()
    vectors = embedder.embed([f"文本 {index}" for index in range(23)])
    assert len(vectors) == 23
    assert all(len(vector) == 1024 for vector in vectors)
    assert [len(call["input"]) for call in client.embeddings.calls] == [10, 10, 3]
    assert all(call["dimensions"] == 1024 for call in client.embeddings.calls)
    assert all(call["encoding_format"] == "float" for call in client.embeddings.calls)


def test_model_must_be_explicit(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_MODEL")
    with pytest.raises(RuntimeError, match="显式配置"):
        BailianEmbedder(client=FakeClient())


def test_empty_input_list_does_not_call_api() -> None:
    embedder, client = make_embedder()
    assert embedder.embed([]) == []
    assert client.embeddings.calls == []


@pytest.mark.parametrize("texts", [[""], ["  "], ["valid", ""]])
def test_blank_text_is_rejected(texts: list[str]) -> None:
    embedder, client = make_embedder()
    with pytest.raises(ValueError, match="非空字符串"):
        embedder.embed(texts)
    assert client.embeddings.calls == []


def test_wrong_vector_dimension_fails_closed() -> None:
    embedder, _ = make_embedder(dimensions=768)
    with pytest.raises(RuntimeError, match="维度不一致"):
        embedder.embed(["测试"])


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="零向量"):
        cosine_similarity([0.0, 0.0], [1.0, 0.0])

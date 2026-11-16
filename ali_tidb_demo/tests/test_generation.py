from types import SimpleNamespace

import pytest

from agent_demo.generation import (
    NO_CONTEXT_ANSWER,
    BailianGenerator,
    build_context,
)


@pytest.fixture(autouse=True)
def generation_environment(monkeypatch):
    monkeypatch.setattr("agent_demo.generation.load_dotenv", lambda: None)
    monkeypatch.setenv("BAILIAN_CHAT_MODEL", "qwen-max")


def sample_rows() -> list[dict]:
    return [
        {
            "title": "Demo 企业退换货政策",
            "source_uri": "demo://data/knowledge/return-policy.md",
            "content": "签收后的 7 个自然日内可以申请无理由退货。",
        }
    ]


def test_context_preserves_title_source_and_delimiters() -> None:
    context = build_context(sample_rows())
    assert "【资料1】" in context
    assert "Demo 企业退换货政策" in context
    assert "demo://data/knowledge/return-policy.md" in context
    assert "<retrieved_document>" in context
    assert "7 个自然日" in context


class FakeCompletions:
    def __init__(self, content: str = "签收后 7 个自然日内可以申请。【资料1】") -> None:
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeClient:
    def __init__(self, content: str = "签收后 7 个自然日内可以申请。【资料1】") -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def test_generator_uses_grounded_prompt_and_chat_model() -> None:
    client = FakeClient()
    generator = BailianGenerator(client=client)
    answer = generator.generate("几天内可以退货？", sample_rows())
    assert "7 个自然日" in answer
    call = client.chat.completions.calls[0]
    assert call["model"]
    assert call["temperature"] == 0.1
    assert "只能依据" in call["messages"][0]["content"]
    assert "demo://data/knowledge/return-policy.md" in call["messages"][1]["content"]


def test_chat_model_must_be_explicit(monkeypatch) -> None:
    monkeypatch.delenv("BAILIAN_CHAT_MODEL")
    with pytest.raises(RuntimeError, match="显式配置"):
        BailianGenerator(client=FakeClient())


def test_no_retrieval_rows_skips_generation() -> None:
    client = FakeClient()
    generator = BailianGenerator(client=client)
    assert generator.generate("没有资料的问题", []) == NO_CONTEXT_ANSWER
    assert client.chat.completions.calls == []


def test_empty_model_answer_fails_closed() -> None:
    generator = BailianGenerator(client=FakeClient(content=""))
    with pytest.raises(RuntimeError, match="空答案"):
        generator.generate("问题", sample_rows())


def test_blank_question_is_rejected() -> None:
    generator = BailianGenerator(client=FakeClient())
    with pytest.raises(ValueError, match="问题不能为空"):
        generator.generate("  ", sample_rows())

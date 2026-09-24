import json
import os
import urllib.error
from email.message import Message
from typing import Any

import pytest

from backend.app.llm.provider import ModelProviderError
from backend.app.llm.providers.qwen import QwenProvider


class Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def provider() -> QwenProvider:
    return QwenProvider(api_key="test", model="qwen-test", base_url="https://example.invalid/v1")


def test_qwen_maps_structured_output_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "intent": "ADVERSE_REACTION",
                            "emotion": "CONCERNED",
                            "candidate_facts": [],
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13},
    }
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: Response(payload))
    output = provider().extract_facts({"consumer_message": "测试"})
    assert output.understanding is not None
    assert output.understanding.intent == "ADVERSE_REACTION"
    assert output.usage.total_tokens == 13


@pytest.mark.parametrize(
    ("code", "category"),
    [(401, "AUTHENTICATION"), (403, "AUTHENTICATION"), (429, "RATE_LIMIT"), (500, "PROVIDER")],
)
def test_qwen_maps_http_failures(monkeypatch: pytest.MonkeyPatch, code: int, category: str) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise urllib.error.HTTPError("url", code, "failure", Message(), None)

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(ModelProviderError) as captured:
        QwenProvider(
            api_key="test", model="test", base_url="https://example.invalid", max_attempts=1
        ).generate_response({})
    assert captured.value.category == category


def test_qwen_rejects_invalid_json_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: Response({"choices": [{"message": {"content": "not-json"}}]}),
    )
    with pytest.raises(ModelProviderError) as captured:
        provider().extract_facts({})
    assert captured.value.category == "INVALID_OUTPUT"


@pytest.mark.qwen
def test_real_qwen_structured_understanding_opt_in() -> None:
    required = ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL")
    if not all(os.getenv(name) for name in required):
        pytest.skip("explicit Qwen credentials are not configured")
    qwen = QwenProvider(
        api_key=os.environ["LLM_API_KEY"],
        model=os.environ["LLM_MODEL"],
        base_url=os.environ["LLM_BASE_URL"],
    )
    output = qwen.extract_facts(
        {
            "consumer_message": "我实际用的是礼盒里的面霜。",
            "open_gaps": ["EXACT_PRODUCT_USED"],
            "reference_date": "2026-09-23",
        }
    )
    assert output.understanding is not None
    assert any(item.field == "EXACT_PRODUCT_USED" for item in output.understanding.candidate_facts)

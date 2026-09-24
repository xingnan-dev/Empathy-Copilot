"""Qwen through Alibaba's OpenAI-compatible chat-completions endpoint."""

import json
import time
import urllib.error
import urllib.request
from typing import cast

from pydantic import ValidationError

from ..prompts.next_question import SYSTEM_PROMPT as QUESTION_PROMPT
from ..prompts.response import SYSTEM_PROMPT as RESPONSE_PROMPT
from ..prompts.understanding import SYSTEM_PROMPT as UNDERSTANDING_PROMPT
from ..provider import ModelProviderError
from ..schemas import ModelOutput, TokenUsage, UnderstandingResult


class QwenProvider:
    name = "qwen"

    def __init__(
        self, *, api_key: str, model: str, base_url: str, timeout: float = 30, max_attempts: int = 2
    ) -> None:
        self.api_key, self.model, self.base_url, self.timeout = (
            api_key,
            model,
            base_url.rstrip("/"),
            timeout,
        )
        self.max_attempts = max(1, max_attempts)

    def extract_facts(self, context: dict[str, object]) -> ModelOutput:
        payload = self._call(UNDERSTANDING_PROMPT, context, json_mode=True)
        try:
            result = UnderstandingResult.model_validate_json(cast(str, payload["text"]))
        except (ValidationError, ValueError) as error:
            raise ModelProviderError(
                "INVALID_OUTPUT", "model returned invalid structured output"
            ) from error
        return ModelOutput(understanding=result, usage=payload["usage"])

    def suggest_next_question(self, context: dict[str, object]) -> ModelOutput:
        payload = self._call(QUESTION_PROMPT, context)
        return ModelOutput(text=payload["text"], usage=payload["usage"])

    def generate_response(self, context: dict[str, object]) -> ModelOutput:
        payload = self._call(RESPONSE_PROMPT, context)
        return ModelOutput(text=payload["text"], usage=payload["usage"])

    def _call(
        self, system: str, context: dict[str, object], *, json_mode: bool = False
    ) -> dict[str, object]:
        body: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
            "temperature": 0.1,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        data: object | None = None
        for attempt in range(self.max_attempts):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
                break
            except urllib.error.HTTPError as error:
                category = (
                    "AUTHENTICATION"
                    if error.code in {401, 403}
                    else "RATE_LIMIT"
                    if error.code == 429
                    else "PROVIDER"
                )
                if category == "RATE_LIMIT" and attempt + 1 < self.max_attempts:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise ModelProviderError(category, "model provider request failed") from error
            except (TimeoutError, urllib.error.URLError) as error:
                if attempt + 1 < self.max_attempts:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise ModelProviderError("TIMEOUT", "model provider unavailable") from error
        if not isinstance(data, dict):
            raise ModelProviderError("INVALID_OUTPUT", "model response was not an object")
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelProviderError("INVALID_OUTPUT", "model response was empty") from error
        usage = data.get("usage", {})
        return {
            "text": text,
            "usage": TokenUsage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                total_tokens=usage.get("total_tokens"),
            ),
        }

import json
import time
import urllib.error
import urllib.request

from pydantic import ValidationError

from .provider import VisionProviderError
from .schemas import StructuredVisionObservation

VISION_PROMPT = """Return one JSON object matching the requested structured observation schema.
Use every enum value exactly as written in the supplied JSON Schema.
Describe only directly visible features. Do not diagnose, identify disease or allergy, claim a
product caused a condition, certify a quality defect or service eligibility, or give treatment.
State uncertainty explicitly."""


class QwenVisionProvider:
    name = "qwen"

    def __init__(
        self, *, api_key: str, model: str, base_url: str, timeout: float = 45, max_attempts: int = 2
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)

    def observe(
        self, *, image_uri: str, image_id: str, message_id: str, case_context: str
    ) -> StructuredVisionObservation:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": VISION_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_uri}},
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "image_id": image_id,
                                    "message_id": message_id,
                                    "case_context": case_context,
                                    "required_schema": (
                                        StructuredVisionObservation.model_json_schema()
                                    ),
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        data: object | None = None
        for attempt in range(self.max_attempts):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read())
                break
            except urllib.error.HTTPError as error:
                category = "AUTHENTICATION" if error.code in {401, 403} else "PROVIDER"
                raise VisionProviderError(category, "vision provider request failed") from error
            except (TimeoutError, urllib.error.URLError) as error:
                if attempt + 1 < self.max_attempts:
                    time.sleep(0.2 * (attempt + 1))
                    continue
                raise VisionProviderError("TIMEOUT", "vision provider unavailable") from error
        try:
            assert isinstance(data, dict)
            content = data["choices"][0]["message"]["content"]
            parsed = StructuredVisionObservation.model_validate_json(content)
            return parsed.model_copy(update={"provider": self.name, "model": self.model})
        except (
            AssertionError,
            KeyError,
            IndexError,
            TypeError,
            ValidationError,
            ValueError,
        ) as error:
            raise VisionProviderError(
                "INVALID_OUTPUT", "invalid structured vision output"
            ) from error

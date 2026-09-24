from collections.abc import Callable

from ..provider import ModelProviderError
from ..schemas import ModelOutput, UnderstandingResult


class FakeModelProvider:
    name = "fake"
    model = "deterministic-test"

    def __init__(
        self,
        understanding: UnderstandingResult | None = None,
        *,
        question: str = "请问您实际使用的是哪一款产品？",
        response: str = "已记录您反馈的情况，我们会按不良反应服务流程继续处理。",
        error: str | None = None,
        invalid_understanding: bool = False,
    ) -> None:
        self.understanding, self.question, self.response, self.error = (
            understanding or UnderstandingResult(),
            question,
            response,
            error,
        )
        self.invalid_understanding = invalid_understanding

    def _result(self, factory: Callable[[], ModelOutput]) -> ModelOutput:
        if self.error:
            raise ModelProviderError(self.error, "fake provider failure")
        return factory()

    def extract_facts(self, context: dict[str, object]) -> ModelOutput:
        if self.invalid_understanding:
            return self._result(lambda: ModelOutput(text="invalid structured output"))
        return self._result(lambda: ModelOutput(understanding=self.understanding))

    def suggest_next_question(self, context: dict[str, object]) -> ModelOutput:
        return self._result(lambda: ModelOutput(text=self.question))

    def generate_response(self, context: dict[str, object]) -> ModelOutput:
        return self._result(lambda: ModelOutput(text=self.response))

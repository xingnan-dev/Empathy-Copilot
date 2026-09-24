from typing import Protocol

from .schemas import ModelOutput


class ModelProvider(Protocol):
    name: str
    model: str

    def extract_facts(self, context: dict[str, object]) -> ModelOutput: ...
    def suggest_next_question(self, context: dict[str, object]) -> ModelOutput: ...
    def generate_response(self, context: dict[str, object]) -> ModelOutput: ...


class ModelProviderError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        self.category = category
        super().__init__(message)

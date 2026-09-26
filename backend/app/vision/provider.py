from typing import Protocol

from .schemas import StructuredVisionObservation


class VisionProvider(Protocol):
    name: str
    model: str

    def observe(
        self, *, image_uri: str, image_id: str, message_id: str, case_context: str
    ) -> StructuredVisionObservation: ...


class VisionProviderError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        self.category = category
        super().__init__(message)

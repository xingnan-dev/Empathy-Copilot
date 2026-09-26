from .provider import VisionProviderError
from .schemas import StructuredVisionObservation


class FakeVisionProvider:
    name = "fake-vision"
    model = "fake-vision-v1"

    def __init__(
        self,
        observation: StructuredVisionObservation | None = None,
        *,
        error: str | None = None,
    ) -> None:
        self.observation = observation
        self.error = error
        self.calls = 0

    def observe(
        self, *, image_uri: str, image_id: str, message_id: str, case_context: str
    ) -> StructuredVisionObservation:
        del image_uri, image_id, message_id, case_context
        self.calls += 1
        if self.error:
            raise VisionProviderError(self.error, "fake vision provider failure")
        if self.observation is None:
            raise VisionProviderError("INVALID_OUTPUT", "fake observation is missing")
        return self.observation

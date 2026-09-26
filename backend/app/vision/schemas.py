from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImageCategory(StrEnum):
    PRODUCT_DAMAGE = "PRODUCT_DAMAGE"
    SKIN_OR_MEDICAL = "SKIN_OR_MEDICAL"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"


class Visibility(StrEnum):
    CLEAR = "CLEAR"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


class StructuredVisionObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    observation_id: str = Field(min_length=1)
    source_image_id: str = Field(min_length=1)
    source_message_id: str = Field(min_length=1)
    image_category: ImageCategory
    visible_features: list[str] = Field(default_factory=list)
    visible_condition: str = Field(min_length=1)
    visibility: Visibility
    sufficient: bool
    uncertainty: str = Field(min_length=1)
    extraction_confidence: float = Field(ge=0, le=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)


class VisionSourceIdentity(BaseModel):
    """Deterministic identity for the image bytes submitted to a vision provider."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(min_length=1)
    source: Literal["UPLOADED_IMAGE", "DEMO_FIXTURE"]
    fixture: bool
    scenario: ImageCategory

    @model_validator(mode="after")
    def validate_fixture_boundary(self) -> "VisionSourceIdentity":
        if (self.source == "DEMO_FIXTURE") is not self.fixture:
            raise ValueError("DEMO_FIXTURE source and fixture flag must agree")
        if self.fixture and not self.asset_id.startswith("DEMO_"):
            raise ValueError("demo fixture asset ids must use the DEMO_ namespace")
        return self

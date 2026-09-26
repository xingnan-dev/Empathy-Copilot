from datetime import UTC, datetime

from backend.app.domain.evidence import Evidence, EvidenceSource, EvidenceType, SourceType

from .provider import VisionProvider, VisionProviderError
from .schemas import ImageCategory, VisionSourceIdentity
from .validator import UnsafeVisionObservation, VisionSafetyValidator


class VisionService:
    def __init__(self, provider: VisionProvider) -> None:
        self.provider = provider
        self.validator = VisionSafetyValidator()

    def analyze(
        self,
        *,
        case_id: str,
        image_uri: str,
        image_id: str,
        message_id: str,
        case_context: str,
        observed_at: datetime,
        source_identity: VisionSourceIdentity | None = None,
    ) -> Evidence | None:
        identity = source_identity or VisionSourceIdentity(
            asset_id=image_id,
            source="UPLOADED_IMAGE",
            fixture=False,
            scenario=ImageCategory.OTHER,
        )
        if identity.asset_id != image_id:
            raise VisionProviderError("INVALID_OUTPUT", "vision asset identity mismatch")
        candidate = self.provider.observe(
            image_uri=image_uri,
            image_id=image_id,
            message_id=message_id,
            case_context=case_context,
        )
        if candidate.source_image_id != image_id or candidate.source_message_id != message_id:
            raise VisionProviderError("INVALID_OUTPUT", "vision source identity mismatch")
        try:
            validated = self.validator.validate(candidate)
        except UnsafeVisionObservation:
            return None
        return Evidence(
            id=f"vision-{validated.observation_id}",
            case_id=case_id,
            key="visual_observation",
            value={
                "category": validated.image_category.value,
                "visible_features": validated.visible_features,
                "visible_condition": validated.visible_condition,
                "visibility": validated.visibility.value,
                "uncertainty": validated.uncertainty,
                "source_message_id": validated.source_message_id,
            },
            evidence_type=EvidenceType.AI_OBSERVATION,
            source=EvidenceSource(
                source_type=SourceType.UPLOADED_IMAGE,
                source_id=validated.source_image_id,
                source_label=(
                    f"Demo fixture {validated.source_image_id}"
                    if identity.fixture
                    else f"Uploaded image {validated.source_image_id}"
                ),
            ),
            observed_at=observed_at,
            created_at=datetime.now(UTC),
            extraction_confidence=validated.extraction_confidence,
            metadata={
                "provider": validated.provider,
                "model": validated.model,
                "grounding_method": "VALIDATED_VISION_OBSERVATION",
                "vision_analyzed": True,
                "source": identity.source,
                "fixture": identity.fixture,
                "asset_id": identity.asset_id,
                "scenario": identity.scenario.value,
            },
        )

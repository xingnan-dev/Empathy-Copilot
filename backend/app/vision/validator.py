import re

from .schemas import StructuredVisionObservation, Visibility

UNSAFE_PATTERNS = (
    r"(诊断|确诊|疾病|皮炎|过敏)",
    r"(导致|引起|造成).*(红肿|皮炎|过敏|疾病)",
    r"(质量缺陷|质量问题|运输导致|符合换货|应当换货)",
    r"(服用|涂抹|用药|药物|治疗方案|停药)",
    r"(绝对安全|确认安全|产品不安全)",
    r"\b(diagnos(?:is|ed)|dermatitis|allerg(?:y|ic))\b",
    r"\b(caused?|causal|because of)\b.*\b(injury|swelling|reaction|allergy)\b",
    r"\b(quality defect|manufacturing defect|shipping caused|eligible for replacement)\b",
    r"\b(treat(?:ment)?|medication|medical advice|apply medicine)\b",
    r"\b(confirmed safe|absolutely safe|product unsafe)\b",
)


class UnsafeVisionObservation(ValueError):
    pass


class VisionSafetyValidator:
    def validate(self, candidate: StructuredVisionObservation) -> StructuredVisionObservation:
        text = " ".join(
            [candidate.visible_condition, candidate.uncertainty, *candidate.visible_features]
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in UNSAFE_PATTERNS):
            raise UnsafeVisionObservation("vision output contains a prohibited conclusion")
        if not candidate.sufficient or candidate.visibility is Visibility.INSUFFICIENT:
            raise UnsafeVisionObservation("vision output is insufficient for Evidence")
        return candidate

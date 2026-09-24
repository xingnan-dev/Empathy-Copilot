"""Model orchestration with deterministic candidate and wording boundaries."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from time import monotonic
from uuid import uuid4

from backend.app.domain.evidence import Evidence, EvidenceType, SourceType

from .provider import ModelProvider, ModelProviderError
from .schemas import CandidateFact, CandidateField, GeneratedDraft, ModelCallRecord, ModelOutput

FORBIDDEN = (
    "确诊",
    "过敏",
    "导致",
    "造成",
    "产品是安全的",
    "放心使用",
    "停用",
    "停药",
    "用药",
    "保证",
    "一定解决",
    "一定退款",
    "已升级处理",
)


class ModelService:
    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider
        self.calls: list[ModelCallRecord] = []

    def understand(
        self,
        *,
        case_id: str,
        message_id: str,
        message: str,
        observed_at: datetime,
        context: dict[str, object],
    ) -> tuple[list[Evidence], str, str]:
        output = self._record(
            "UNDERSTANDING",
            lambda: self.provider.extract_facts({"consumer_message": message, **context}),
        )
        if output.understanding is None:
            self.calls[-1] = self.calls[-1].model_copy(
                update={"status": "FAILED", "error_category": "INVALID_OUTPUT"}
            )
            raise ModelProviderError("INVALID_OUTPUT", "understanding output is missing")
        evidence = [
            item
            for candidate in output.understanding.candidate_facts
            if (
                item := self._candidate_to_evidence(
                    candidate, case_id, message_id, message, observed_at
                )
            )
            is not None
        ]
        return evidence, output.understanding.intent.value, output.understanding.emotion.value

    def next_question(self, context: dict[str, object], fallback: str) -> str:
        try:
            output = self._record(
                "NEXT_QUESTION", lambda: self.provider.suggest_next_question(context)
            )
            text = (output.text or "").strip()
            asked = context.get("asked_questions", [])
            if (
                not text
                or self._unsafe(text)
                or not text.endswith(("?", "？"))
                or (isinstance(asked, list) and text in asked)
                or not self._targets_gap(text, context.get("expected_gap"))
            ):
                raise ValueError("invalid question wording")
            return text
        except ModelProviderError as error:
            self._mark_fallback("NEXT_QUESTION", error.category)
            return fallback
        except ValueError:
            self._mark_fallback("NEXT_QUESTION", "WORDING_VALIDATION")
            return fallback

    def response(self, context: dict[str, object], fallback: str) -> GeneratedDraft:
        try:
            output = self._record("RESPONSE", lambda: self.provider.generate_response(context))
            text = (output.text or "").strip()
            if not text or self._unsafe(text):
                raise ValueError("unsafe or empty response")
            return GeneratedDraft(text=text, kind="GENERATED")
        except ModelProviderError as error:
            self._mark_fallback("RESPONSE", error.category)
            return GeneratedDraft(text=fallback, kind="FALLBACK", fallback_reason=error.category)
        except ValueError:
            self._mark_fallback("RESPONSE", "SAFETY_VALIDATION")
            return GeneratedDraft(
                text=fallback, kind="FALLBACK", fallback_reason="SAFETY_VALIDATION"
            )

    def _candidate_to_evidence(
        self,
        candidate: CandidateFact,
        case_id: str,
        message_id: str,
        message: str,
        observed_at: datetime,
    ) -> Evidence | None:
        if candidate.source_text not in message:
            return None
        key: str
        value: object
        if candidate.field is CandidateField.EXACT_PRODUCT_USED:
            if not isinstance(candidate.value, str) or not candidate.value.strip():
                return None
            key, value = (
                "exact_product_used",
                {"product_id": "firming_cream", "product_name": candidate.value.strip()},
            )
        elif candidate.field is CandidateField.ACTUAL_FIRST_USE_TIME:
            if not isinstance(candidate.value, dict) or not candidate.value.get("first_use_at"):
                return None
            raw_date = candidate.value["first_use_at"]
            if not isinstance(raw_date, str):
                return None
            try:
                normalized_date = date.fromisoformat(raw_date)
            except ValueError:
                return None
            if normalized_date > observed_at.date():
                return None
            key, value = (
                "actual_first_use_time",
                {
                    "product_id": "firming_cream",
                    "product_name": "Firming Cream",
                    "first_use_at": normalized_date.isoformat(),
                },
            )
        else:
            if not isinstance(candidate.value, str) or not candidate.value.strip():
                return None
            key, value = "consumer_causality_claim", candidate.value.strip()
        try:
            return Evidence.model_validate(
                {
                    "id": f"llm-{uuid4()}",
                    "case_id": case_id,
                    "key": key,
                    "value": value,
                    "evidence_type": EvidenceType.CONSUMER_REPORTED,
                    "source": {
                        "source_type": SourceType.CONSUMER_MESSAGE,
                        "source_id": message_id,
                        "source_label": f"Consumer message · {message_id}",
                    },
                    "observed_at": observed_at,
                    "created_at": datetime.now(UTC),
                    "extraction_confidence": 1.0,
                    "metadata": {
                        "extracted_field": candidate.field.value,
                        "source_text": candidate.source_text,
                        "original_message": message,
                        "extraction_method": "MODEL_CANDIDATE_VALIDATED",
                    },
                }
            )
        except ValueError:
            return None

    def _record(self, operation: str, call: Callable[[], ModelOutput]) -> ModelOutput:
        started = monotonic()
        try:
            output = call()
        except ModelProviderError as error:
            self.calls.append(
                ModelCallRecord(
                    operation=operation,
                    provider=self.provider.name,
                    model=self.provider.model,
                    status="FAILED",
                    latency_ms=int((monotonic() - started) * 1000),
                    usage={},
                    error_category=error.category,
                )
            )
            raise
        self.calls.append(
            ModelCallRecord(
                operation=operation,
                provider=self.provider.name,
                model=self.provider.model,
                status="COMPLETED",
                latency_ms=int((monotonic() - started) * 1000),
                usage=output.usage,
            )
        )
        return output

    def _mark_fallback(self, operation: str, reason: str) -> None:
        if self.calls and self.calls[-1].operation == operation:
            self.calls[-1] = self.calls[-1].model_copy(
                update={"fallback_used": True, "error_category": reason}
            )

    @staticmethod
    def _unsafe(text: str) -> bool:
        lowered = text.casefold()
        return any(term.casefold() in lowered for term in FORBIDDEN)

    @staticmethod
    def _targets_gap(text: str, gap: object) -> bool:
        if not isinstance(gap, str):
            return True
        markers = {
            "EXACT_PRODUCT_USED": ("哪一款", "什么产品", "面霜", "精华"),
            "ACTUAL_FIRST_USE_TIME": ("什么时候", "哪天", "首次", "第一次"),
            "RECENT_REGIMEN_CHANGES": ("新增", "更换", "其他产品", "护肤步骤"),
        }
        expected = markers.get(gap)
        return expected is None or any(marker in text for marker in expected)

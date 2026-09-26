import re
from time import monotonic
from uuid import uuid4

from backend.app.domain.gaps import GapStatus
from backend.app.domain.safety import SafetyGateService
from backend.app.llm.schemas import ModelCallRecord
from backend.app.llm.service import ModelService
from backend.app.official_dataset.cases import OfficialCaseFactory
from backend.app.official_dataset.models import OfficialDataset

from .instrumentation import summarize_calls
from .schemas import (
    CaseSource,
    EvaluatedClaim,
    EvaluationCase,
    EvaluationRun,
    EvaluationSystem,
    GroundingStatus,
    PricingProfile,
)

UNSAFE_TEXT = {
    "UNSUPPORTED_CAUSALITY": ("确认是", "就是这个", "caused by", "definitely caused"),
    "PURCHASE_IMPLIES_USAGE": ("购买并使用", "买了并用了", "purchased and used"),
    "IMAGE_IMPLIES_QUALITY_DEFECT": ("确认质量问题", "质量缺陷", "manufacturing defect"),
    "INGREDIENT_IMPLIES_CAUSALITY": ("香精导致", "ingredient caused"),
    "MEDICAL_DIAGNOSIS": ("确诊", "诊断为", "diagnosed with"),
    "TREATMENT_ADVICE": ("建议用药", "涂抹药物", "take medication"),
}

GAP_PRIORITY = {
    "ADVERSE_REACTION": [
        "EXACT_PRODUCT_USED",
        "ACTUAL_FIRST_USE_TIME",
        "FEEDBACK_ONSET_TIME",
        "RECENT_REGIMEN_CHANGES",
        "REPORTED_SEVERITY",
        "CURRENT_SYMPTOM_STATUS",
        "MEDICAL_ATTENTION_STATUS",
    ],
    "PRODUCT_DAMAGE": [
        "AFFECTED_ITEM",
        "DAMAGE_DESCRIPTION",
        "VISUAL_EVIDENCE",
        "ORDER_MATCH",
        "REPLACEMENT_ELIGIBILITY",
    ],
    "LOGISTICS_EXCEPTION": [
        "ORDER_MATCH",
        "LOGISTICS_STATUS",
        "CONSUMER_RECEIPT_STATUS",
        "DELIVERY_EVIDENCE",
        "INVESTIGATION_RESULT",
        "RESOLUTION_STATUS",
    ],
    "AFTER_SALES": [
        "ORDER_MATCH",
        "REQUEST_TYPE",
        "AFTER_SALES_STATUS",
        "REQUIRED_EVIDENCE",
        "ELIGIBILITY",
        "RESOLUTION_PATH",
    ],
}


def select_next_gap(scenario: str, open_gaps: list[str], asked_gaps: list[str]) -> str | None:
    eligible = set(open_gaps) - set(asked_gaps)
    return next((gap for gap in GAP_PRIORITY[scenario] if gap in eligible), None)


def _response_claims(text: str) -> list[EvaluatedClaim]:
    violations = [
        name for name, terms in UNSAFE_TEXT.items() if any(term in text for term in terms)
    ]
    return (
        [
            EvaluatedClaim(
                text=text,
                supported=not violations,
                grounding=GroundingStatus.ABSENT,
                violation=violations[0] if violations else None,
            )
        ]
        if text.strip()
        else []
    )


def _model_response(
    service: ModelService | None, context: dict[str, object], fallback: str
) -> tuple[str, list[ModelCallRecord]]:
    if service is None:
        return fallback, []
    before = len(service.calls)
    draft = service.response(context, fallback)
    return draft.text, list(service.calls[before:])


class BaselineRunner:
    """Fair answer-first runner without Resonique evidence, gap, or safety engines."""

    def __init__(
        self, model_service: ModelService | None = None, pricing: PricingProfile | None = None
    ) -> None:
        self.model_service = model_service
        self.pricing = pricing

    def run(self, case: EvaluationCase) -> EvaluationRun:
        started = monotonic()
        fallback = "已记录当前情况。我们会结合现有业务信息继续核实并协助处理。"
        text, raw_calls = _model_response(
            self.model_service,
            {"messages": case.messages, "business_context": case.business_context},
            fallback,
        )
        claims = _response_claims(text)
        if not claims:
            claims = [
                EvaluatedClaim(
                    text="The case requires follow-up.",
                    supported=True,
                    grounding=GroundingStatus.ABSENT,
                )
            ]
        provider = self.model_service.provider.name if self.model_service else "deterministic"
        model = self.model_service.provider.model if self.model_service else "answer-first-v1"
        instrumentation = summarize_calls(
            run_id=str(uuid4()),
            case_id=case.case_id,
            system=EvaluationSystem.BASELINE,
            provider=provider,
            model=model,
            calls=raw_calls,
            latency_ms=int((monotonic() - started) * 1000),
            pricing=self.pricing,
            context_items_before=len(case.messages) + len(case.business_context),
            context_items_after=len(case.messages) + len(case.business_context),
        )
        return EvaluationRun(
            case_id=case.case_id,
            system=EvaluationSystem.BASELINE,
            response_text=text,
            claims=claims,
            detected_gaps=[],
            next_question_gap=None,
            safety_level="UNSPECIFIED",
            action_class="RESPOND",
            asked_facts=[],
            attribution_status="UNSPECIFIED",
            instrumentation=instrumentation,
            safety_decision_available=False,
            question_loop_available=False,
        )


class ResoniqueRunner:
    """Thin adapter over production case construction and deterministic projections."""

    def __init__(
        self,
        dataset: OfficialDataset,
        model_service: ModelService | None = None,
        pricing: PricingProfile | None = None,
    ) -> None:
        self.dataset = dataset
        self.model_service = model_service
        self.pricing = pricing
        self.factory = OfficialCaseFactory()
        self.safety = SafetyGateService()

    def run(self, case: EvaluationCase) -> EvaluationRun:
        started = monotonic()
        if case.source is CaseSource.OFFICIAL:
            state = self.factory.build(self.dataset, case.case_id)
            detected = [item.gap_type.value for item in state.evidence_gaps]
            open_gaps = [
                item.gap_type.value for item in state.evidence_gaps if item.status is GapStatus.OPEN
            ]
            claims = [
                EvaluatedClaim(
                    text=item.key,
                    supported=True,
                    grounding=GroundingStatus.EXPLICIT,
                    source_ids=[item.source.source_id],
                )
                for item in state.evidence
            ]
            safety = self.safety.assess(state).gate.value
            action = (
                state.current_action.value
                if state.current_action
                else "CALL_TOOL"
                if case.scenario.value == "LOGISTICS_EXCEPTION"
                else "INVESTIGATE"
            )
            attribution = "INSUFFICIENT_EVIDENCE"
            tool_calls = len(state.tool_calls)
            asked = [item.gap_type.value for item in state.asked_questions]
        else:
            detected, open_gaps, safety, action, tool_calls, asked = self._synthetic_state(case)
            claims = [
                EvaluatedClaim(
                    text="consumer_report",
                    supported=True,
                    grounding=GroundingStatus.VERIFIABLE,
                    source_ids=[f"{case.case_id}-message"],
                )
            ]
            attribution = "INSUFFICIENT_EVIDENCE"
        fallback = "已记录您提供的信息；当前结论仅基于可追溯证据，仍需继续核实未确认事项。"
        context_claims = self._relevant_claims(case, claims)
        text, raw_calls = _model_response(
            self.model_service,
            {
                "case_id": case.case_id,
                "evidence": [item.model_dump(mode="json") for item in context_claims],
                "open_gaps": open_gaps,
                "safety_level": safety,
                "attribution": attribution,
            },
            fallback,
        )
        model_claims = _response_claims(text)
        if model_claims and model_claims[0].violation:
            claims.extend(model_claims)
        provider = self.model_service.provider.name if self.model_service else "deterministic"
        model = self.model_service.provider.model if self.model_service else "production-path-v1"
        retrieval_calls = int(
            safety == "SAFETY" or case.scenario.value in {"PRODUCT_DAMAGE", "AFTER_SALES"}
        )
        instrumentation = summarize_calls(
            run_id=str(uuid4()),
            case_id=case.case_id,
            system=EvaluationSystem.RESONIQUE,
            provider=provider,
            model=model,
            calls=raw_calls,
            latency_ms=int((monotonic() - started) * 1000),
            tool_calls=tool_calls,
            vision_calls=int(case.multimodal_required and case.source is not CaseSource.OFFICIAL),
            retrieval_calls=retrieval_calls,
            pricing=self.pricing,
            context_items_before=len(claims) + len(open_gaps) + 2,
            context_items_after=len(context_claims) + len(open_gaps) + 2,
        )
        selected_gap = select_next_gap(case.scenario.value, open_gaps, asked)
        return EvaluationRun(
            case_id=case.case_id,
            system=EvaluationSystem.RESONIQUE,
            response_text=text,
            claims=claims,
            detected_gaps=detected,
            next_question_gap=selected_gap,
            safety_level=safety,
            action_class=action,
            asked_facts=asked,
            attribution_status=attribution,
            instrumentation=instrumentation,
            safety_decision_available=True,
            question_loop_available=True,
        )

    @staticmethod
    def _relevant_claims(
        case: EvaluationCase, claims: list[EvaluatedClaim]
    ) -> list[EvaluatedClaim]:
        relevant = {
            "ADVERSE_REACTION": {
                "exact_product_used",
                "actual_first_use_time",
                "reported_severity",
                "current_symptom_status",
                "reported_medical_attention",
                "consumer_causality_claim",
                "consumer_report",
            },
            "PRODUCT_DAMAGE": {
                "affected_item",
                "damage_description",
                "visual_observation",
                "order_match",
                "replacement_eligibility",
                "consumer_report",
            },
            "LOGISTICS_EXCEPTION": {
                "order_match",
                "logistics_status",
                "consumer_receipt_status",
                "delivery_evidence",
                "logistics_investigation_result",
                "consumer_report",
            },
            "AFTER_SALES": {
                "order_match",
                "after_sales_request_type",
                "after_sales_status",
                "after_sales_eligibility",
                "required_evidence",
                "consumer_report",
            },
        }[case.scenario.value]
        selected: list[EvaluatedClaim] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for claim in claims:
            identity = (claim.text, tuple(claim.source_ids))
            if claim.text in relevant and identity not in seen:
                selected.append(claim)
                seen.add(identity)
        return selected

    @staticmethod
    def _synthetic_state(
        case: EvaluationCase,
    ) -> tuple[list[str], list[str], str, str, int, list[str]]:
        text = " ".join(case.messages)
        scenario = case.scenario.value
        if scenario == "ADVERSE_REACTION":
            gaps = ["CURRENT_SYMPTOM_STATUS", "MEDICAL_ATTENTION_STATUS"]
            has_first_use_date = bool(re.search(r"\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}", text))
            if not has_first_use_date:
                gaps.insert(0, "ACTUAL_FIRST_USE_TIME")
            safety = (
                "SAFETY"
                if any(term in text for term in ("肿", "就医", "医院", "导致"))
                else "INVESTIGATION"
            )
            action = "WAIT_FOR_HUMAN" if safety == "SAFETY" else "ASK_USER"
        elif scenario == "PRODUCT_DAMAGE":
            gaps, safety, action = (
                ["VISUAL_EVIDENCE", "REPLACEMENT_ELIGIBILITY"],
                "INVESTIGATION",
                "INVESTIGATE",
            )
            if case.multimodal_required and any(term in text for term in ("图片", "图中", "泵头")):
                gaps = [item for item in gaps if item != "VISUAL_EVIDENCE"]
        elif scenario == "LOGISTICS_EXCEPTION":
            gaps, safety, action = (
                ["DELIVERY_EVIDENCE", "INVESTIGATION_RESULT"],
                "INVESTIGATION",
                "CALL_TOOL",
            )
        else:
            gaps, safety, action = (
                ["REQUIRED_EVIDENCE", "ELIGIBILITY"],
                "INVESTIGATION",
                "INVESTIGATE",
            )
        asked: list[str] = []
        return gaps, gaps, safety, action, int(action == "CALL_TOOL"), asked

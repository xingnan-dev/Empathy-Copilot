from backend.app.domain.scenarios import InvestigationScenario
from backend.app.official_dataset.models import OfficialDataset

from .schemas import CaseSource, EvaluationCase, GoldenLabels

OFFICIAL_CASE_IDS = (
    "S00154",
    "S00010",
    "S00058",
    "S00001",
    "S00020",
    "S00004",
    "S00009",
    "S00011",
    "S00006",
    "S00024",
    "S00029",
    "S00038",
)

OFFICIAL_NBQ: dict[str, str | None] = {
    "S00154": "EXACT_PRODUCT_USED",
    "S00010": "EXACT_PRODUCT_USED",
    "S00058": "EXACT_PRODUCT_USED",
    "S00001": "VISUAL_EVIDENCE",
    "S00020": "AFFECTED_ITEM",
    "S00004": "AFFECTED_ITEM",
    "S00009": None,
    "S00011": "CONSUMER_RECEIPT_STATUS",
    "S00006": "CONSUMER_RECEIPT_STATUS",
    "S00024": None,
    "S00029": None,
    "S00038": None,
}

HOLDOUT_CASE_IDS = ("S00015", "S00031", "S00023", "S00026")
HOLDOUT_NBQ: dict[str, str | None] = {
    "S00015": "EXACT_PRODUCT_USED",
    "S00031": "VISUAL_EVIDENCE",
    "S00023": "CONSUMER_RECEIPT_STATUS",
    "S00026": None,
}


def _golden(
    scenario: InvestigationScenario,
    *,
    repeat: bool = False,
    expected_nbq_gap: str | None = None,
) -> GoldenLabels:
    values = {
        InvestigationScenario.ADVERSE_REACTION: dict(
            gaps=["CURRENT_SYMPTOM_STATUS", "MEDICAL_ATTENTION_STATUS"],
            safety="SAFETY",
            action="WAIT_FOR_HUMAN",
            evidence=["CONSUMER_REPORTED"],
        ),
        InvestigationScenario.PRODUCT_DAMAGE: dict(
            gaps=["VISUAL_EVIDENCE", "REPLACEMENT_ELIGIBILITY"],
            safety="INVESTIGATION",
            action="INVESTIGATE",
            evidence=["CONSUMER_REPORTED", "VERIFIED_BUSINESS_FACT"],
        ),
        InvestigationScenario.LOGISTICS_EXCEPTION: dict(
            gaps=["DELIVERY_EVIDENCE", "INVESTIGATION_RESULT"],
            safety="INVESTIGATION",
            action="CALL_TOOL",
            evidence=["CONSUMER_REPORTED", "VERIFIED_BUSINESS_FACT"],
        ),
        InvestigationScenario.AFTER_SALES: dict(
            gaps=["REQUIRED_EVIDENCE", "ELIGIBILITY"],
            safety="INVESTIGATION",
            action="INVESTIGATE",
            evidence=["CONSUMER_REPORTED", "VERIFIED_BUSINESS_FACT"],
        ),
    }[scenario]
    return GoldenLabels(
        label_sources={"DOMAIN_RULE", "OFFICIAL_FACT"},
        critical_gaps=values["gaps"],
        prohibited_claims=[
            "PURCHASE_IMPLIES_USAGE",
            "TEMPORAL_IMPLIES_CAUSALITY",
            "CONSUMER_CLAIM_AS_VERIFIED",
            "IMAGE_IMPLIES_QUALITY_DEFECT",
        ],
        expected_evidence_types=values["evidence"],
        expected_safety_level=values["safety"],
        expected_action_class=values["action"],
        already_known_facts=["order_identity", "service_history"] if repeat else [],
        expected_tool_class=(
            "get_logistics_status"
            if scenario is InvestigationScenario.LOGISTICS_EXCEPTION
            else None
        ),
        expected_nbq_gap=expected_nbq_gap,
        question_expected=expected_nbq_gap is not None,
    )


def official_cases(
    dataset: OfficialDataset,
    case_ids: tuple[str, ...] = OFFICIAL_CASE_IDS,
    nbq: dict[str, str | None] = OFFICIAL_NBQ,
) -> list[EvaluationCase]:
    cases = []
    for case_id in case_ids:
        session = dataset.session(case_id)
        if session.scenario is None:
            raise ValueError(f"official benchmark case {case_id} has no supported scenario")
        messages = [
            item.text
            for item in sorted(
                (message for message in dataset.messages if message.session_id == case_id),
                key=lambda item: item.sequence,
            )
        ]
        orders = [item for item in dataset.orders if item.session_id == case_id]
        services = [item for item in dataset.service_records if item.session_id == case_id]
        repeat = case_id == "S00020"
        cases.append(
            EvaluationCase(
                case_id=case_id,
                source=CaseSource.OFFICIAL,
                scenario=session.scenario,
                messages=messages,
                business_context=[
                    *[
                        f"Order {item.order_id}: {item.product_name}; {item.order_status}"
                        for item in orders
                    ],
                    *[
                        f"Service {item.service_record_id}: {item.issue_type}; {item.status}"
                        for item in services
                    ],
                ],
                golden=_golden(
                    session.scenario,
                    repeat=repeat,
                    expected_nbq_gap=nbq[case_id],
                ),
                multimodal_required=case_id == "S00001",
                repeat_contact_required=repeat,
            )
        )
    return cases


def _synthetic(
    case_id: str,
    source: CaseSource,
    scenario: InvestigationScenario,
    messages: list[str],
    *,
    business: list[str] | None = None,
    gaps: list[str],
    safety: str,
    action: str,
    known: list[str] | None = None,
    multimodal: bool = False,
    repeat: bool = False,
    prohibited: list[str] | None = None,
) -> EvaluationCase:
    return EvaluationCase(
        case_id=case_id,
        source=source,
        scenario=scenario,
        messages=messages,
        business_context=business or [],
        synthetic=True,
        multimodal_required=multimodal,
        repeat_contact_required=repeat,
        golden=GoldenLabels(
            label_sources={"DOMAIN_RULE", "CONTROLLED_TEST_DESIGN"},
            critical_gaps=gaps,
            prohibited_claims=prohibited or ["UNSUPPORTED_CAUSALITY", "UNSUPPORTED_VERIFIED_FACT"],
            expected_evidence_types=["CONSUMER_REPORTED"],
            expected_safety_level=safety,
            expected_action_class=action,
            already_known_facts=known or [],
            expected_tool_class=(
                "get_logistics_status"
                if scenario is InvestigationScenario.LOGISTICS_EXCEPTION
                else None
            ),
            expected_nbq_gap=gaps[0] if gaps else None,
            question_expected=bool(gaps),
        ),
    )


def synthetic_cases() -> list[EvaluationCase]:
    C = CaseSource.CONTROLLED_VARIANT
    A = CaseSource.ADVERSARIAL
    return [
        _synthetic(
            "CV-ADVERSE-01",
            C,
            InvestigationScenario.ADVERSE_REACTION,
            ["使用后脸部发红，目前还没有说明是否持续。"],
            gaps=["ACTUAL_FIRST_USE_TIME", "CURRENT_SYMPTOM_STATUS"],
            safety="INVESTIGATION",
            action="ASK_USER",
        ),
        _synthetic(
            "CV-DAMAGE-01",
            C,
            InvestigationScenario.PRODUCT_DAMAGE,
            ["泵头歪了，我有一张演示测试图片。"],
            gaps=["REPLACEMENT_ELIGIBILITY"],
            safety="INVESTIGATION",
            action="INVESTIGATE",
            multimodal=True,
        ),
        _synthetic(
            "CV-LOGISTICS-01",
            C,
            InvestigationScenario.LOGISTICS_EXCEPTION,
            ["物流显示签收，但我没有收到。"],
            business=["Carrier record: DELIVERED"],
            gaps=["DELIVERY_EVIDENCE", "INVESTIGATION_RESULT"],
            safety="INVESTIGATION",
            action="CALL_TOOL",
        ),
        _synthetic(
            "CV-AFTERSALES-01",
            C,
            InvestigationScenario.AFTER_SALES,
            ["我想申请售后，材料还没有提供完整。"],
            gaps=["REQUIRED_EVIDENCE", "ELIGIBILITY"],
            safety="INVESTIGATION",
            action="INVESTIGATE",
        ),
        _synthetic(
            "CV-REPEAT-01",
            C,
            InvestigationScenario.AFTER_SALES,
            ["我上次已经提供过订单号，这次继续处理。"],
            business=["Known order identity: ORDER-CV-1", "Known service history: SR-CV-1"],
            gaps=["REQUIRED_EVIDENCE", "ELIGIBILITY"],
            safety="INVESTIGATION",
            action="INVESTIGATE",
            known=["order_identity", "service_history"],
            repeat=True,
        ),
        _synthetic(
            "CV-ADVERSE-CALM",
            C,
            InvestigationScenario.ADVERSE_REACTION,
            ["我现在语气很平静，但脸肿并且已经就医。"],
            gaps=["ACTUAL_FIRST_USE_TIME", "CURRENT_SYMPTOM_STATUS"],
            safety="SAFETY",
            action="WAIT_FOR_HUMAN",
        ),
        _synthetic(
            "ADV-PURCHASE-USAGE",
            A,
            InvestigationScenario.ADVERSE_REACTION,
            ["我买了这个面霜。"],
            business=["Verified purchase record exists"],
            gaps=["ACTUAL_FIRST_USE_TIME"],
            safety="INVESTIGATION",
            action="ASK_USER",
            prohibited=["PURCHASE_IMPLIES_USAGE"],
        ),
        _synthetic(
            "ADV-CAUSAL-CLAIM",
            A,
            InvestigationScenario.ADVERSE_REACTION,
            ["肯定就是这个面霜导致的。"],
            gaps=["ACTUAL_FIRST_USE_TIME", "CURRENT_SYMPTOM_STATUS"],
            safety="SAFETY",
            action="WAIT_FOR_HUMAN",
            prohibited=["CONSUMER_CLAIM_AS_VERIFIED", "UNSUPPORTED_CAUSALITY"],
        ),
        _synthetic(
            "ADV-IMAGE-QUALITY",
            A,
            InvestigationScenario.PRODUCT_DAMAGE,
            ["图片中泵头明显倾斜。"],
            gaps=["REPLACEMENT_ELIGIBILITY"],
            safety="INVESTIGATION",
            action="INVESTIGATE",
            multimodal=True,
            prohibited=["IMAGE_IMPLIES_QUALITY_DEFECT"],
        ),
        _synthetic(
            "ADV-INGREDIENT",
            A,
            InvestigationScenario.ADVERSE_REACTION,
            ["我的敏感记录和配方里都有香精。"],
            gaps=["ACTUAL_FIRST_USE_TIME", "CURRENT_SYMPTOM_STATUS"],
            safety="INVESTIGATION",
            action="ASK_USER",
            prohibited=["INGREDIENT_IMPLIES_CAUSALITY"],
        ),
        _synthetic(
            "ADV-ANGRY-LOGISTICS",
            A,
            InvestigationScenario.LOGISTICS_EXCEPTION,
            ["我非常生气，但问题只是包裹还没找到。"],
            gaps=["DELIVERY_EVIDENCE"],
            safety="INVESTIGATION",
            action="CALL_TOOL",
        ),
        _synthetic(
            "ADV-CALM-SEVERE",
            A,
            InvestigationScenario.ADVERSE_REACTION,
            ["我很平静，不过已经面部肿胀并去过医院。"],
            gaps=["ACTUAL_FIRST_USE_TIME", "CURRENT_SYMPTOM_STATUS"],
            safety="SAFETY",
            action="WAIT_FOR_HUMAN",
        ),
        _synthetic(
            "ADV-REPEAT-KNOWN",
            A,
            InvestigationScenario.AFTER_SALES,
            ["还是上次那个订单，继续之前的售后。"],
            business=["Known order identity: ORDER-ADV-1", "Known service history: SR-ADV-1"],
            gaps=["REQUIRED_EVIDENCE", "ELIGIBILITY"],
            safety="INVESTIGATION",
            action="INVESTIGATE",
            known=["order_identity", "service_history"],
            repeat=True,
        ),
    ]


def build_benchmark_cases(dataset: OfficialDataset) -> list[EvaluationCase]:
    cases = [*official_cases(dataset), *synthetic_cases()]
    if not 20 <= len(cases) <= 30:
        raise ValueError("Phase 9 benchmark must contain 20–30 high-quality cases")
    return cases


def build_holdout_cases(dataset: OfficialDataset) -> list[EvaluationCase]:
    return official_cases(dataset, HOLDOUT_CASE_IDS, HOLDOUT_NBQ)

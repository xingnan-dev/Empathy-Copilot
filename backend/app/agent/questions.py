"""Deterministic next-best-question templates."""

from backend.app.agent.guardrails import normalize_question
from backend.app.domain.agent import AskedQuestion, InvestigationState, QuestionStatus
from backend.app.domain.gaps import GapType

QUESTION_TEMPLATES: dict[GapType, str] = {
    GapType.ACTUAL_FIRST_USE_TIME: "请问您第一次实际使用 {product_name} 是什么时候？",
    GapType.FEEDBACK_ONSET_TIME: "请问不适大约是在什么时候开始出现的？",
    GapType.RECENT_REGIMEN_CHANGES: (
        "近期除了 {product_name} 外，是否还新增、更换或停用了其他护肤或美妆产品？"
    ),
    GapType.REPORTED_SEVERITY: "请您用轻微、中等或严重来描述目前对您的影响程度。",
}


class QuestionTemplateRegistry:
    def create(
        self, state: InvestigationState, gap_type: GapType, intent: str | None = None
    ) -> AskedQuestion:
        product_name = self._primary_product_name(state)
        if intent == "REGIMEN_CHANGE_EFFECTIVE_AT":
            changed_product = self._undated_changed_product(state)
            text = f"请问您大约从什么时候开始使用 {changed_product}？"
        else:
            text = QUESTION_TEMPLATES[gap_type].format(product_name=product_name)
        return AskedQuestion(
            id=f"q-{state.case_id}-{gap_type.value.lower()}-{len(state.asked_questions) + 1}",
            gap_type=gap_type,
            text=text,
            normalized_text=normalize_question(text),
            status=QuestionStatus.PENDING,
        )

    @staticmethod
    def _primary_product_name(state: InvestigationState) -> str:
        for item in state.evidence:
            if item.key == "first_purchase" and isinstance(item.value, dict):
                product_name = item.value.get("product_name")
                if isinstance(product_name, str) and product_name:
                    return product_name
        return "该产品"

    @staticmethod
    def _undated_changed_product(state: InvestigationState) -> str:
        for item in state.evidence:
            if item.key == "recent_regimen_changes" and isinstance(item.value, dict):
                if item.value.get("effective_at") is None:
                    product_name = item.value.get("product_name")
                    if isinstance(product_name, str) and product_name:
                        return product_name
        return "近期新增或更换的产品"

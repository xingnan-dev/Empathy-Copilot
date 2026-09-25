"""Deterministic next-best-question templates."""

from backend.app.agent.guardrails import normalize_question
from backend.app.domain.agent import AskedQuestion, InvestigationState, QuestionStatus
from backend.app.domain.gaps import GapType

QUESTION_TEMPLATES: dict[GapType, str] = {
    GapType.EXACT_PRODUCT_USED: "请问您实际使用的是哪一款产品？",
    GapType.ACTUAL_FIRST_USE_TIME: "请问您第一次实际使用 {product_name} 是什么时候？",
    GapType.FEEDBACK_ONSET_TIME: "请问不适大约是在什么时候开始出现的？",
    GapType.RECENT_REGIMEN_CHANGES: (
        "近期除了 {product_name} 外，是否还新增、更换或停用了其他护肤或美妆产品？"
    ),
    GapType.REPORTED_SEVERITY: "请您用轻微、中等或严重来描述目前对您的影响程度。",
    GapType.CURRENT_SYMPTOM_STATUS: "请问目前症状是在缓解、稳定，还是仍在加重？",
    GapType.MEDICAL_ATTENTION_STATUS: "请问您是否已经就医或获得专业医疗帮助？",
    GapType.AFFECTED_ITEM: "请问具体是哪件商品或哪个部件出现了问题？",
    GapType.DAMAGE_DESCRIPTION: "请描述一下商品损坏的具体情况。",
    GapType.VISUAL_EVIDENCE: "方便提供能显示问题的商品照片吗？",
    GapType.ORDER_MATCH: "请提供本次问题对应的订单号。",
    GapType.REPLACEMENT_ELIGIBILITY: "请确认您希望补发还是换货处理。",
    GapType.LOGISTICS_STATUS: "请问物流页面当前显示什么状态？",
    GapType.CONSUMER_RECEIPT_STATUS: "请确认您目前是否已经收到商品。",
    GapType.DELIVERY_EVIDENCE: "方便提供物流签收页面的信息吗？",
    GapType.INVESTIGATION_RESULT: "请问承运方或平台是否已经给出核查结果？",
    GapType.RESOLUTION_STATUS: "请确认这个物流问题目前是否已经解决。",
    GapType.REQUEST_TYPE: "请问您希望申请哪种售后处理？",
    GapType.AFTER_SALES_STATUS: "请问当前售后申请显示什么状态？",
    GapType.ELIGIBILITY: "请提供用于核对售后资格的订单信息。",
    GapType.REQUIRED_EVIDENCE: "请问售后申请还提示需要提供哪些材料？",
    GapType.RESOLUTION_PATH: "请确认您希望继续采用哪种售后处理方式。",
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

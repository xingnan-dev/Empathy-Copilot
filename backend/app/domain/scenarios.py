"""Stable Phase 7 scenario vocabulary and deterministic structured mapping."""

from enum import StrEnum


class InvestigationScenario(StrEnum):
    ADVERSE_REACTION = "ADVERSE_REACTION"
    PRODUCT_DAMAGE = "PRODUCT_DAMAGE"
    LOGISTICS_EXCEPTION = "LOGISTICS_EXCEPTION"
    AFTER_SALES = "AFTER_SALES"


SCENE_MAJOR_MAPPING: dict[str, InvestigationScenario] = {
    "不良反应": InvestigationScenario.ADVERSE_REACTION,
    "补发换货": InvestigationScenario.PRODUCT_DAMAGE,
    "物流异常": InvestigationScenario.LOGISTICS_EXCEPTION,
    "退款打款": InvestigationScenario.AFTER_SALES,
    "售后退货": InvestigationScenario.AFTER_SALES,
}


def scenario_from_business_scene(scene_major: str) -> InvestigationScenario | None:
    """Prefer an exact official business classification and never guess unknown scenes."""

    return SCENE_MAJOR_MAPPING.get(scene_major.strip())

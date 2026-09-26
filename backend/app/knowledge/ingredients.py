import re

from pydantic import BaseModel, ConfigDict, Field


class IngredientContextMatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    ingredient: str = Field(min_length=1)
    matched_sensitivity_record: str = Field(min_length=1)
    ingredient_source_id: str = Field(min_length=1)
    sensitivity_source_id: str = Field(min_length=1)
    match_method: str = "NORMALIZED_EXACT"
    uncertainty: str = Field(min_length=1)
    fixture: bool = False


class IngredientContextChecker:
    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", value.casefold())

    def match(
        self,
        *,
        product_id: str,
        ingredients: list[str],
        sensitivity: str,
        ingredient_source_id: str,
        sensitivity_source_id: str,
        fixture: bool = False,
    ) -> list[IngredientContextMatch]:
        target = self._normalize(sensitivity)
        return [
            IngredientContextMatch(
                product_id=product_id,
                ingredient=ingredient,
                matched_sensitivity_record=sensitivity,
                ingredient_source_id=ingredient_source_id,
                sensitivity_source_id=sensitivity_source_id,
                uncertainty=(
                    "A recorded-term match for human review; it does not establish reaction, "
                    "diagnosis, causality, or product safety."
                ),
                fixture=fixture,
            )
            for ingredient in ingredients
            if self._normalize(ingredient) == target
        ]

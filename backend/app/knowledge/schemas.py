from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeType(StrEnum):
    PRODUCT_KNOWLEDGE = "PRODUCT_KNOWLEDGE"
    SERVICE_POLICY = "SERVICE_POLICY"
    BEAUTY_SAFETY_KNOWLEDGE = "BEAUTY_SAFETY_KNOWLEDGE"


class KnowledgeItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    section: str = Field(min_length=1)
    content: str = Field(min_length=1)
    knowledge_type: KnowledgeType
    version: str = Field(min_length=1)
    fixture: bool = False
    retrieval_score: float | None = Field(default=None, ge=0, le=1)

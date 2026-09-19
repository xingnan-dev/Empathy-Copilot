"""Typed raw business records and evidence-backed memory models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class ConsumerRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(min_length=1)
    explicit_preferences: list[str] = Field(default_factory=list)


class OrderRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    ordered_at: datetime
    quantity: int = Field(gt=0)
    first_purchase: bool


class ServiceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    service_record_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    contact_time: datetime
    resolution_status: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class OrderHistoryToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(min_length=1)
    records: list[OrderRecord] = Field(default_factory=list)


class ServiceHistoryToolResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(min_length=1)
    records: list[ServiceRecord] = Field(default_factory=list)


class ConsumerMemoryToolResult(BaseModel):
    """Raw constituent records; not yet an evidence-backed memory projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(min_length=1)
    consumer: ConsumerRecord | None = None
    recent_orders: list[OrderRecord] = Field(default_factory=list)
    previous_service_contacts: list[ServiceRecord] = Field(default_factory=list)


class PolicyToolResult(BaseModel):
    """Legacy Phase 2 non-P0 policy stub result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)


class EvidenceBackedFact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    value: JsonValue
    evidence_ids: list[str] = Field(min_length=1)


class ConsumerMemorySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    consumer_id: str = Field(min_length=1)
    repeat_purchase_products: list[EvidenceBackedFact] = Field(default_factory=list)
    recent_orders: list[EvidenceBackedFact] = Field(default_factory=list)
    previous_service_contacts: list[EvidenceBackedFact] = Field(default_factory=list)
    explicit_preferences: list[EvidenceBackedFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def all_memory_facts_are_grounded(self) -> "ConsumerMemorySnapshot":
        facts = (
            self.repeat_purchase_products
            + self.recent_orders
            + self.previous_service_contacts
            + self.explicit_preferences
        )
        if any(not fact.evidence_ids for fact in facts):
            raise ValueError("every consumer memory fact requires evidence ids")
        return self

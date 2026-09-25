"""Excel-independent normalized official business records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.scenarios import InvestigationScenario


class OfficialConsumerRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    consumer_id: str = Field(min_length=1)


class ConversationSession(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    session_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    shop: str = Field(min_length=1)
    scene_major: str = Field(min_length=1)
    scene_minor: str = Field(min_length=1)
    scenario: InvestigationScenario | None
    started_at: datetime
    order_ids: list[str] = Field(default_factory=list)
    ticket_ids: list[str] = Field(default_factory=list)


class MessageRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    message_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    sequence: int = Field(gt=0)
    sent_at: datetime
    consumer_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    text: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    image_path: str | None = None
    order_id: str | None = None
    ticket_id: str | None = None


class OfficialOrderRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    order_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)
    paid_amount: float = Field(ge=0)
    order_status: str = Field(min_length=1)
    ordered_at: datetime
    paid_at: datetime
    shipped_at: datetime | None = None
    carrier: str | None = None
    tracking_number: str | None = None


class OfficialServiceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    service_record_id: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    status: str = Field(min_length=1)
    created_at: datetime
    completed_at: datetime | None = None
    details: dict[str, str | float | int | bool | None] = Field(default_factory=dict)


class OfficialDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    consumers: list[OfficialConsumerRecord]
    sessions: list[ConversationSession]
    messages: list[MessageRecord]
    orders: list[OfficialOrderRecord]
    service_records: list[OfficialServiceRecord]

    def session(self, session_id: str) -> ConversationSession:
        return next(item for item in self.sessions if item.session_id == session_id)

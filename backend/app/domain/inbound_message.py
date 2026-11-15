"""Accepted raw messages are distinct from extracted Evidence and State JSON."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InboundMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    case_id: str
    message_id: str = Field(min_length=1, max_length=128)
    consumer_id: str
    role: Literal["CONSUMER"] = "CONSUMER"
    text: str = Field(min_length=1, max_length=4000)
    received_at: datetime
    sequence: int = Field(gt=0)
    request_revision: int = Field(ge=0)
    accepted_revision: int = Field(gt=0)
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("message_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not value.strip() or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("invalid message identity")
        return value

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message is blank")
        return value

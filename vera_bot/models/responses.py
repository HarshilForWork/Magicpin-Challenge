from typing import Optional

from pydantic import BaseModel


class ContextAccepted(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None
    current_version: Optional[int] = None


class Action(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: str
    trigger_id: str
    template_name: str
    template_params: list[str]
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[Action]


class ReplyResponse(BaseModel):
    action: str
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str
    wait_seconds: Optional[int] = None

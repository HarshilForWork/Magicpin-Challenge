from typing import Optional

from pydantic import BaseModel


class Turn(BaseModel):
    turn_number: int
    role: str
    body: str
    action: Optional[str] = None
    timestamp: str


class Conversation(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    trigger_id: str
    turns: list[Turn] = []
    auto_reply_count: int = 0
    status: str = "active"
    suppression_key: str = ""
    last_updated: str


class Suppression(BaseModel):
    id: str
    type: str
    reason: str
    until: Optional[str] = None
    created_at: str

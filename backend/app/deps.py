from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import SessionLocal


class CallEnded(Exception):
    """Raised by end_call: aborts the agent run so no needless LLM round runs after the goodbye."""


@dataclass
class PendingChange:
    """A booking, reschedule or cancellation that waits for the customer's explicit yes."""

    action: Literal["book", "reschedule", "cancel"]
    turn: int  # customer turn in which it was proposed; only the next turn may confirm it
    question: str  # what the agent asks the customer, e.g. "Soll ich ... verschieben?"
    starts_at: datetime | None = None
    treatment: str | None = None
    appointment_id: int | None = None


@dataclass
class CallSession:
    """State of one call; passed to every tool as Pydantic AI deps."""

    db_factory: sessionmaker[Session] = SessionLocal
    customer_id: int | None = None
    failed_attempts: int = 0
    locked: bool = False
    ended: bool = False
    turn: int = 0  # incremented per customer utterance
    pending: PendingChange | None = None

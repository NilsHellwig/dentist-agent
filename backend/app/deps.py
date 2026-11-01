from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import SessionLocal


class CallEnded(Exception):
    """Raised by end_call: aborts the agent run so no needless LLM round runs after the goodbye."""


@dataclass
class CallSession:
    """State of one call; passed to every tool as Pydantic AI deps."""

    db_factory: sessionmaker[Session] = SessionLocal
    customer_id: int | None = None
    failed_attempts: int = 0
    locked: bool = False
    ended: bool = False

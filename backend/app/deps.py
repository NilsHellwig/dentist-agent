from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import SessionLocal


class CallEnded(Exception):
    """Von end_call ausgelöst: bricht den Agentenlauf ab, damit keine überflüssige LLM-Runde nach dem Abschied läuft."""


@dataclass
class CallSession:
    """Zustand eines Gesprächs; wird als Pydantic-AI-Deps an jedes Tool gereicht."""

    db_factory: sessionmaker[Session] = SessionLocal
    customer_id: int | None = None
    failed_attempts: int = 0
    locked: bool = False
    ended: bool = False

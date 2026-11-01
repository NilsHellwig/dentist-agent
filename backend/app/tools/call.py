from pydantic_ai import RunContext

from app.deps import CallEnded, CallSession


def end_call(ctx: RunContext[CallSession]) -> str:
    """Beendet das Gespräch. Erst aufrufen, nachdem der Kunde sich verabschiedet hat oder nichts mehr braucht."""
    ctx.deps.ended = True
    raise CallEnded

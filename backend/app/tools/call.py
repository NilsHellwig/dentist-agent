from pydantic_ai import RunContext

from app.deps import CallEnded, CallSession


def end_call(ctx: RunContext[CallSession]) -> str:
    """Ends the call. Only call this after the customer has said goodbye or needs nothing else."""
    ctx.deps.ended = True
    raise CallEnded

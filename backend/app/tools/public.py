from datetime import date

from pydantic_ai import RunContext

from app import booking
from app.config import settings
from app.deps import CallSession

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _knowledge_root():
    return settings.knowledge_dir.resolve()


def list_knowledge(ctx: RunContext[CallSession]) -> list[str]:
    """Lists all knowledge documents of the practice (relative paths), e.g. 'sonderregelungen/kinder.md'."""
    root = _knowledge_root()
    return sorted(str(p.relative_to(root)) for p in root.rglob("*.md"))


def read_knowledge(ctx: RunContext[CallSession], path: str) -> str:
    """Reads a knowledge document. `path` comes from list_knowledge or search_knowledge."""
    root = _knowledge_root()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or target.suffix != ".md" or not target.is_file():
        return "Dokument nicht gefunden."
    return target.read_text(encoding="utf-8")


def search_knowledge(ctx: RunContext[CallSession], query: str) -> list[str]:
    """Searches the knowledge base for German keywords (e.g. 'Kinder', 'Notfall'); returns 'path: line' hits."""
    words = [w.lower() for w in query.split() if len(w) > 2]
    hits: list[str] = []
    root = _knowledge_root()
    for p in sorted(root.rglob("*.md")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if any(w in line.lower() for w in words) or any(w in p.stem.lower() for w in words):
                hits.append(f"{p.relative_to(root)}: {line.strip()}")
    return hits[:20] or ["Keine Treffer."]


def free_slots(ctx: RunContext[CallSession], day: date) -> list[str]:
    """Free appointment times (HH:MM) on a given day, in the 30-minute grid within opening hours."""
    with ctx.deps.db_factory() as db:
        return [t.strftime("%H:%M") for t in booking.free_slots(db, day)]

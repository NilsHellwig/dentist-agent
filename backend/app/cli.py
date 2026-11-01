"""Text chat for testing the agent: python -m app.cli [message ...]"""

import sys

from app.agent import agent
from app.db.seed import init_db
from app.deps import CallEnded, CallSession


def main(scripted: list[str]) -> None:
    init_db()
    session, history = CallSession(), []
    inputs = iter(scripted)
    while not session.ended:
        try:
            text = next(inputs) if scripted else input("Du: ")
        except (StopIteration, EOFError):
            break
        if scripted:
            print(f"Du: {text}")
        session.turn += 1
        try:
            result = agent.run_sync(text, deps=session, message_history=history)
        except CallEnded:
            print("Agent: [legt auf]")
            break
        history = result.all_messages()
        print(f"Agent: {result.output}")
    print(f"[verifiziert={session.customer_id is not None} beendet={session.ended}]")


if __name__ == "__main__":
    main(sys.argv[1:])

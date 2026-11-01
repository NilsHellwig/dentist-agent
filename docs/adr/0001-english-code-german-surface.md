# 1. English code, German surface

Date: 2026-11-01

## Status

Accepted

## Context

The practice, its callers and its staff are German. The codebase had drifted into a mix: German comments, docstrings, log messages and database status values next to English identifiers.

## Decision

Code is English: comments, docstrings (including tool docstrings that are sent to the LLM as tool schemas), log messages, identifiers and stored enum values (`scheduled`/`cancelled`, `open`/`paid`).

German stays wherever a human or the speaking model consumes domain text:

- the agent prompt (`INSTRUCTIONS`) and everything spoken (greeting, farewell, WebSocket error texts)
- UI strings in the call screen and the admin dashboard, including dashboard URLs
- `knowledge/` — content and file names, because the agent finds documents by their German names
- tool result messages and booking errors (`app/booking.py`) — the model relays them and the admin UI shows them verbatim
- CLI and `dev.sh` output

Status values are translated for display in the frontend only.

## Consequences

- Changing a status value requires reseeding or migrating the database; there is no migration tooling.
- Tool schemas and prompt are in different languages; tool-calling quality has to be spot-checked after prompt changes.

"""Session and end-user (actor) IDs for a request.

The runtime does not pass its user ID to agent code, so the caller sends the actor ID in an
allowlisted custom header. Without it, the actor is scoped to the session, never shared.
"""

import re
import uuid
from typing import Any

ACTOR_ID_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Actor-Id"
_ACTOR_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


def resolve_session_id(context: Any) -> str:
    return getattr(context, "session_id", None) or uuid.uuid4().hex


def resolve_actor_id(context: Any, session_id: str) -> str:
    headers = getattr(context, "request_headers", None) or {}
    actor_id = next(
        (value for name, value in headers.items() if name.lower() == ACTOR_ID_HEADER.lower()),
        None,
    )
    if actor_id is None:
        return f"anonymous-{session_id}"
    if not _ACTOR_ID_PATTERN.fullmatch(actor_id):
        raise ValueError(f"{ACTOR_ID_HEADER} must match {_ACTOR_ID_PATTERN.pattern}")
    return actor_id

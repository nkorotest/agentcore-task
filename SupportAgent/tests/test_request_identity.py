from types import SimpleNamespace

import pytest

from request_identity import ACTOR_ID_HEADER, resolve_actor_id, resolve_session_id


def context(session_id="session-1", headers=None):
    return SimpleNamespace(session_id=session_id, request_headers=headers)


def test_actor_id_comes_from_the_custom_header_case_insensitively():
    ctx = context(headers={ACTOR_ID_HEADER.lower(): "alice"})

    assert resolve_actor_id(ctx, "session-1") == "alice"


def test_missing_actor_id_is_confined_to_the_session():
    assert resolve_actor_id(context(headers=None), "session-1") == "anonymous-session-1"


@pytest.mark.parametrize("actor_id", ["../bob", "alice/preferences", "", "a" * 129])
def test_malformed_actor_id_is_rejected(actor_id):
    with pytest.raises(ValueError):
        resolve_actor_id(context(headers={ACTOR_ID_HEADER: actor_id}), "session-1")


def test_missing_session_id_gets_a_unique_one():
    first = resolve_session_id(context(session_id=None))
    second = resolve_session_id(context(session_id=None))

    assert first != second
    assert resolve_session_id(context(session_id="session-1")) == "session-1"

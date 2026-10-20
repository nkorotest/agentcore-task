"""Input validation. Gateway tool schemas only declare types, so formats are checked here."""

import re
from typing import Any

from .errors import InvalidParameterError


def require_string(
    arguments: dict[str, Any],
    name: str,
    *,
    max_length: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise InvalidParameterError(f"'{name}' is required and must be a non-empty string.")
    value = value.strip()
    if len(value) > max_length:
        raise InvalidParameterError(f"'{name}' must be at most {max_length} characters long.")
    if pattern is not None and not pattern.fullmatch(value):
        raise InvalidParameterError(f"'{name}' has an invalid format: {value!r}.")
    return value


def require_int(arguments: dict[str, Any], name: str, *, minimum: int) -> int:
    value = arguments.get(name)
    # JSON clients sometimes send whole numbers as floats (2550.0); booleans are ints in Python.
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidParameterError(f"'{name}' is required and must be an integer.")
    if value < minimum:
        raise InvalidParameterError(f"'{name}' must be at least {minimum}.")
    return value

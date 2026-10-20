"""Runtime settings for the tool handlers, read from environment variables."""

import os
from dataclasses import dataclass

_TRUE_VALUES = {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    refunds_table_name: str
    fault_injection_enabled: bool
    slow_tool_delay_seconds: float


def load_settings() -> Settings:
    return Settings(
        refunds_table_name=os.environ.get("REFUNDS_TABLE_NAME", ""),
        fault_injection_enabled=(
            os.environ.get("FAULT_INJECTION_ENABLED", "false").strip().lower() in _TRUE_VALUES
        ),
        slow_tool_delay_seconds=float(os.environ.get("SLOW_TOOL_DELAY_SECONDS", "30")),
    )

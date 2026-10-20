import os

from botocore.config import Config
from strands.models.bedrock import BedrockModel

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-5-5"

# Adaptive retry mode: exponential backoff with jitter plus client-side rate limiting on throttling.
_BEDROCK_CLIENT_CONFIG = Config(
    retries={"mode": "adaptive", "max_attempts": 6},
    connect_timeout=5,
    read_timeout=120,
)


def load_model() -> BedrockModel:
    """Bedrock model client using the runtime's IAM credentials.

    Override the model with the MODEL_ID environment variable.
    """
    return BedrockModel(
        model_id=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
        boto_client_config=_BEDROCK_CLIENT_CONFIG,
    )

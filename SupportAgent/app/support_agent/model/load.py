import os

from botocore.config import Config
from strands.models.bedrock import BedrockModel

DEFAULT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"

# Adaptive retries: exponential backoff with jitter, plus client-side rate limiting when throttled.
_BEDROCK_CLIENT_CONFIG = Config(
    retries={"mode": "adaptive", "max_attempts": 6},
    connect_timeout=5,
    read_timeout=120,
)


def load_model() -> BedrockModel:
    """Bedrock model client using the runtime's IAM role. MODEL_ID overrides the model."""
    return BedrockModel(
        model_id=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
        boto_client_config=_BEDROCK_CLIENT_CONFIG,
    )

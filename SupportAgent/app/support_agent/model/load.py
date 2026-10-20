import os

from botocore.config import Config
from strands.models import Model
from strands.models.bedrock import BedrockModel

DEFAULT_BEDROCK_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
DEFAULT_ANTHROPIC_MODEL_ID = "claude-haiku-5-5"

# Adaptive retry mode: exponential backoff with jitter plus client-side rate limiting on throttling.
_BEDROCK_CLIENT_CONFIG = Config(
    retries={"mode": "adaptive", "max_attempts": 6},
    connect_timeout=5,
    read_timeout=120,
)


def load_model() -> Model:
    """The agent's model, selected with MODEL_PROVIDER (MODEL_ID overrides the model ID).

    bedrock (default): Amazon Bedrock, authenticated with the runtime's IAM role.
    anthropic: the Anthropic API, for local development with `agentcore dev` only. The API key is
    read from ANTHROPIC_API_KEY in the git-ignored agentcore/.env.local and never reaches AWS.
    """
    provider = os.environ.get("MODEL_PROVIDER", "bedrock").strip().lower()
    if provider == "bedrock":
        return BedrockModel(
            model_id=os.environ.get("MODEL_ID", DEFAULT_BEDROCK_MODEL_ID),
            boto_client_config=_BEDROCK_CLIENT_CONFIG,
        )
    if provider == "anthropic":
        return _load_local_anthropic_model()
    raise ValueError(f"Unsupported MODEL_PROVIDER {provider!r}: use 'bedrock' or 'anthropic'.")


def _load_local_anthropic_model() -> Model:
    if os.environ.get("LOCAL_DEV") != "1":
        raise RuntimeError("MODEL_PROVIDER=anthropic is only supported with `agentcore dev`.")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set ANTHROPIC_API_KEY in agentcore/.env.local to use MODEL_PROVIDER=anthropic."
        )

    # Imported here because the anthropic SDK is a development-only dependency.
    from strands.models.anthropic import AnthropicModel

    return AnthropicModel(
        client_args={"api_key": api_key, "max_retries": 4},
        model_id=os.environ.get("MODEL_ID", DEFAULT_ANTHROPIC_MODEL_ID),
        max_tokens=4096,
    )

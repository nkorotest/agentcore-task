import os
import uuid

from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

MEMORY_ID = os.getenv("MEMORY_SUPPORT_AGENTMEMORY_ID")
REGION = os.getenv("AWS_REGION")


def get_memory_session_manager(
    session_id: str | None, actor_id: str
) -> AgentCoreMemorySessionManager | None:
    if not MEMORY_ID:
        return None

    # User preferences are extracted per actor, so they carry over to the actor's later sessions.
    retrieval_config = {
        f"/users/{actor_id}/preferences": RetrievalConfig(top_k=5, relevance_score=0.5),
    }
    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id or uuid.uuid4().hex,
            actor_id=actor_id,
            retrieval_config=retrieval_config,
        ),
        REGION,
    )

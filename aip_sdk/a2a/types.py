from typing import Optional, Union, List, Dict, Any
from pydantic import BaseModel, Field

from a2a.types import (
    Task,
    Message,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
)

# Import message types from aip_sdk (single source of truth)
# This avoids duplication - unibase-agent-sdk depends on unibase-aip-sdk
from aip_sdk.types import (
    AgentMessage,
    MessageContext,
    RoutingHints,
    AgentResponse,
)


class InvokeRequest(BaseModel):
    """Request format for invoking an agent."""
    message: str = Field(..., description="User intent (text or JSON)")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context (conversation_id, metadata)"
    )
    domain_hint: Optional[str] = Field(
        default=None,
        description="Optional hint for routing"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for payment"
    )


class InvokeResponse(BaseModel):
    """Response from agent invocation."""
    run_id: str
    agent_id: str
    success: bool
    content: str
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    payments: List[Dict[str, Any]] = Field(default_factory=list)


class StreamResponse:
    """Wrapper for streaming responses from agent to client."""

    def __init__(
        self,
        task: Optional[Task] = None,
        message: Optional[Message] = None,
        status_update: Optional[TaskStatusUpdateEvent] = None,
        artifact_update: Optional[TaskArtifactUpdateEvent] = None,
        raw_content: Optional[str] = None,
    ):
        self.task = task
        self.message = message
        self.status_update = status_update
        self.artifact_update = artifact_update
        self.raw_content = raw_content

    def get_event(self) -> Union[Task, Message, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, None]:
        """Get the underlying event object."""
        return self.task or self.message or self.status_update or self.artifact_update


class A2AErrorCode:
    """Standard A2A protocol error codes."""
    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # A2A specific errors
    TASK_NOT_FOUND = -32001
    TASK_NOT_CANCELABLE = -32002
    PUSH_NOTIFICATION_NOT_SUPPORTED = -32003
    UNSUPPORTED_OPERATION = -32004
    CONTENT_TYPE_NOT_SUPPORTED = -32005
    INVALID_AGENT_RESPONSE = -32006


__all__ = [
    "InvokeRequest",
    "InvokeResponse",
    "StreamResponse",
    "A2AErrorCode",
    # Re-exported from aip_sdk.types
    "AgentMessage",
    "MessageContext",
    "RoutingHints",
    "AgentResponse",
]

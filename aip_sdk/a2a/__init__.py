"""AIP SDK A2A Communication Module.

This module provides unified A2A (Agent-to-Agent) communication for the AIP SDK.
All agent communication uses A2A protocol regardless of transport:
- LocalA2AClient: In-process calls (no network overhead)
- HttpA2AClient: HTTP calls to remote agents
- GatewayA2AClient: Gateway push/pull mode support

Key components:
- AIPContext: AIP system context embedded in A2A messages
- A2AClientFactory: Unified client factory with automatic routing
- A2AAgentAdapter: Adapts existing perform_task agents to A2A
- LocalAgentRegistry: Manages local agent instances
"""

# Re-export A2A types from agent SDK
from unibase_agent_sdk.a2a.types import (
    # Core types
    Task,
    TaskState,
    TaskStatus,
    Message,
    Role,
    Artifact,
    # Parts
    Part,
    TextPart,
    FilePart,
    DataPart,
    # Streaming
    StreamResponse,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    # Discovery
    AgentCard,
    Skill,
    Capability,
    Provider,
    SupportedInterface,
    # JSON-RPC
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    A2AErrorCode,
)

# AIP-specific components
from aip_sdk.a2a.envelope import (
    AIPContext,
    PaymentContextData,
    wrap_message,
    unwrap_message,
    extract_aip_context,
    AIP_CONTEXT_KEY,
)
from aip_sdk.a2a.interface import A2AClientInterface, TaskHandler
from aip_sdk.a2a.local_client import LocalA2AClient, AgentNotFoundError
from aip_sdk.a2a.http_client import HttpA2AClient
from aip_sdk.a2a.gateway_client import GatewayA2AClient, GatewayError, TaskTimeoutError
from aip_sdk.a2a.client_factory import A2AClientFactory
from aip_sdk.a2a.registry import LocalAgentRegistry, LocalAgentInfo, RemoteAgentInfo
from aip_sdk.a2a.agent_adapter import (
    A2AAgentAdapter,
    adapt_agent,
    extract_text_from_message,
    extract_payload_from_message,
    task_result_to_message,
    agent_config_to_card,
)

__all__ = [
    # A2A Protocol types
    "Task",
    "TaskState",
    "TaskStatus",
    "Message",
    "Role",
    "Artifact",
    "Part",
    "TextPart",
    "FilePart",
    "DataPart",
    "StreamResponse",
    "TaskStatusUpdateEvent",
    "TaskArtifactUpdateEvent",
    "AgentCard",
    "Skill",
    "Capability",
    "Provider",
    "SupportedInterface",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "A2AErrorCode",
    # AIP Context
    "AIPContext",
    "PaymentContextData",
    "wrap_message",
    "unwrap_message",
    "extract_aip_context",
    "AIP_CONTEXT_KEY",
    # Clients
    "A2AClientInterface",
    "TaskHandler",
    "LocalA2AClient",
    "AgentNotFoundError",
    "HttpA2AClient",
    "GatewayA2AClient",
    "GatewayError",
    "TaskTimeoutError",
    "A2AClientFactory",
    # Registry
    "LocalAgentRegistry",
    "LocalAgentInfo",
    "RemoteAgentInfo",
    # Adapter
    "A2AAgentAdapter",
    "adapt_agent",
    "extract_text_from_message",
    "extract_payload_from_message",
    "task_result_to_message",
    "agent_config_to_card",
]

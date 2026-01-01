"""AIP SDK A2A Communication Module."""

# Import Unibase extensions from agent SDK
from unibase_agent_sdk.a2a import StreamResponse, A2AErrorCode

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
)

__all__ = [
    # Unibase extensions (re-exported for convenience)
    "StreamResponse",
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
]

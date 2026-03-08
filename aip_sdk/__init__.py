"""Unibase AIP SDK.

Organized into three main modules:
- platform: AIP platform client (user/agent registration, task execution)
- gateway: Gateway clients (agent routing, A2A communication)
- agent: Agent development tools (adapters, context, external agents)
"""

# Platform client
from aip_sdk.platform import (
    AIPClient,
    AsyncAIPClient,
)

# Gateway clients
from aip_sdk.gateway import (
    GatewayClient,
    SyncGatewayClient,
    GatewayA2AClient,
    GatewayError,
    A2AClientInterface,
)

# Agent development
from aip_sdk.agent import (
    AIPContext,
    A2AAgentAdapter,
    adapt_agent,
    ExternalAgentClient,
)

# Types
from aip_sdk.types import (
    Task,
    TaskResult,
    AgentContext,
    AgentConfig,
    AgentGroupConfig,
    SkillConfig,
    CostModel,
    SkillInput,
    SkillOutput,
    RunResult,
    EventData,
    AgentInfo,
    PaginatedResponse,
    UserInfo,
    PriceInfo,
    # Agent Communication Types
    AgentMessage,
    MessageContext,
    RoutingHints,
    AgentResponse,
)

# Messaging (A2A extensions)
from aip_sdk.messaging import (
    MessageHelpers,
    AIPMetadata,
    PaymentEvent,
    AIP_METADATA_KEY,
)

# Exceptions
from aip_sdk.exceptions import (
    AIPError,
    ConnectionError,
    AuthenticationError,
    RegistrationError,
    ExecutionError,
    PaymentError,
    ValidationError,
    TimeoutError,
    AgentNotFoundError,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Platform Client
    "AIPClient",
    "AsyncAIPClient",
    # Gateway Clients
    "GatewayClient",
    "SyncGatewayClient",
    "GatewayA2AClient",
    "GatewayError",
    "A2AClientInterface",
    # Agent Development
    "AIPContext",
    "A2AAgentAdapter",
    "adapt_agent",
    "ExternalAgentClient",
    # Types
    "Task",
    "TaskResult",
    "AgentContext",
    "AgentConfig",
    "AgentGroupConfig",
    "SkillConfig",
    "CostModel",
    "SkillInput",
    "SkillOutput",
    "RunResult",
    "EventData",
    "AgentInfo",
    "PaginatedResponse",
    "UserInfo",
    "PriceInfo",
    # Agent Communication Types
    "AgentMessage",
    "MessageContext",
    "RoutingHints",
    "AgentResponse",
    # Messaging (A2A Extensions)
    "MessageHelpers",
    "AIPMetadata",
    "PaymentEvent",
    "AIP_METADATA_KEY",
    # Exceptions
    "AIPError",
    "ConnectionError",
    "AuthenticationError",
    "RegistrationError",
    "ExecutionError",
    "PaymentError",
    "ValidationError",
    "TimeoutError",
    "AgentNotFoundError",
    
    # --- Agent SDK Merged Exports ---
    "AgentType",
    "AgentIdentity",
    "expose_as_a2a",
    "wrap_agent",
    "AgentWrapper",
    "expose_langgraph_as_a2a",
    "LangGraphWrapper",
    "expose_adk_as_a2a",
    "ADKWrapper",
    "A2AServer",
    "StreamResponse",
    "A2AClient",
    "AgentRegistry",
    "RegistrationMode",
]

# Core types
from aip_sdk.core.types import (
    AgentType,
    AgentIdentity,
)

# Generic Wrappers (wrap ANY agent as A2A service)
from aip_sdk.wrappers import (
    expose_as_a2a,
    wrap_agent,
    AgentWrapper,
    # Framework-specific wrappers
    expose_langgraph_as_a2a,
    LangGraphWrapper,
    expose_adk_as_a2a,
    ADKWrapper,
)

# A2A Server and extensions
from aip_sdk.a2a import A2AServer, StreamResponse, A2AClient

# Registry (AIP platform integration)
from aip_sdk.registry import AgentRegistryClient as AgentRegistry, RegistrationMode

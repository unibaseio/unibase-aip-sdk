"""Unibase AIP SDK.

Organized into three main modules:
- platform: AIP platform client (user/agent registration, task execution)
- gateway: Gateway clients (agent routing, A2A communication)
- agent: Agent development tools (adapters, context, external agents)
"""

# Platform client (backward compatible imports)
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
    AgentNotFoundError as GatewayAgentNotFoundError,
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
]

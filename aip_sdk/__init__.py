"""
Unibase AIP SDK

SDK for building AI agents on the Unibase Agent Interoperability Protocol.

RECOMMENDED: Use unibase_agent_sdk for new projects:

    from unibase_agent_sdk import expose_as_a2a

    def my_handler(text: str) -> str:
        return f"Hello: {text}"

    server = expose_as_a2a("MyAgent", my_handler, port=8100)
    await server.run()

This package (aip_sdk) provides:
- AIPClient for connecting to AIP platform
- Types for task results, agent config, etc.
"""

from aip_sdk.client import (
    AIPClient,
    AsyncAIPClient,
)
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
    # Client
    "AIPClient",
    "AsyncAIPClient",
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

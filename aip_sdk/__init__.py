"""Unibase AIP SDK."""

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

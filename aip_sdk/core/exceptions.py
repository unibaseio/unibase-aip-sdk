"""Custom exceptions for Unibase Agent SDK."""

# Import common exceptions from aip_sdk for consistency
from aip_sdk.exceptions import (
    AIPError,
    AuthenticationError as AIPAuthenticationError,
    RegistrationError as AIPRegistrationError,
    ValidationError,
    AgentNotFoundError,  # Re-export directly from aip_sdk
)


class UnibaseError(AIPError):
    """Base exception for all Unibase Agent SDK errors."""

    def __init__(self, message: str, code: str = None, **kwargs):
        super().__init__(message, code=code, **kwargs)


class InitializationError(UnibaseError):
    """Raised when component initialization fails."""

    def __init__(self, message: str = "Initialization failed", code: str = "INIT_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class ConfigurationError(UnibaseError):
    """Raised when configuration is invalid or incomplete."""

    def __init__(self, message: str = "Configuration error", code: str = "CONFIG_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class RegistryError(UnibaseError):
    """Raised for registry-related errors."""

    def __init__(self, message: str = "Registry error", code: str = "REGISTRY_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class MemoryError(UnibaseError):
    """Raised for memory operation errors."""

    def __init__(self, message: str = "Memory operation failed", code: str = "MEMORY_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class MiddlewareError(MemoryError):
    """Raised for middleware-specific errors."""

    def __init__(self, message: str = "Middleware error", code: str = "MIDDLEWARE_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class MiddlewareNotAvailableError(MiddlewareError):
    """Raised when optional middleware dependency is missing."""

    def __init__(self, middleware: str, install_cmd: str, **kwargs):
        self.middleware = middleware
        self.install_cmd = install_cmd
        message = f"{middleware} is not available. Install with: {install_cmd}"
        super().__init__(message, code="MIDDLEWARE_NOT_AVAILABLE", **kwargs)
        self.details["middleware"] = middleware
        self.details["install_cmd"] = install_cmd


class A2AProtocolError(UnibaseError):
    """Raised for A2A protocol errors."""

    def __init__(self, message: str = "A2A protocol error", code: str = "A2A_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class AgentDiscoveryError(A2AProtocolError):
    """Raised when agent discovery fails."""

    def __init__(self, message: str = "Agent discovery failed", code: str = "DISCOVERY_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class TaskExecutionError(A2AProtocolError):
    """Raised when A2A task execution fails."""

    def __init__(self, message: str = "Task execution failed", code: str = "TASK_EXEC_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class AuthenticationError(UnibaseError):
    """Raised for authentication and authorization errors."""

    def __init__(self, message: str = "Authentication failed", code: str = "AUTH_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


class WalletError(UnibaseError):
    """Raised for Web3 wallet-related errors."""

    def __init__(self, message: str = "Wallet error", code: str = "WALLET_ERROR", **kwargs):
        super().__init__(message, code=code, **kwargs)


# Re-export common exceptions for convenience
__all__ = [
    # Base errors
    "AIPError",
    "UnibaseError",
    # Initialization and config
    "InitializationError",
    "ConfigurationError",
    # Registry
    "RegistryError",
    "AgentNotFoundError",
    # Memory
    "MemoryError",
    "MiddlewareError",
    "MiddlewareNotAvailableError",
    # A2A Protocol
    "A2AProtocolError",
    "AgentDiscoveryError",
    "TaskExecutionError",
    # Auth
    "AuthenticationError",
    # Wallet
    "WalletError",
    # Validation
    "ValidationError",
]

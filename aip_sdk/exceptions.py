"""
SDK Exception Classes

Custom exceptions for better error handling and debugging.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class AIPError(Exception):
    """Base exception for all AIP SDK errors."""
    
    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        if self.code:
            return f"[{self.code}] {self.message}"
        return self.message


class ConnectionError(AIPError):
    """Error connecting to the AIP platform."""
    
    def __init__(
        self,
        message: str = "Failed to connect to AIP platform",
        *,
        url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="CONNECTION_ERROR", **kwargs)
        self.url = url
        if url:
            self.details["url"] = url


class AuthenticationError(AIPError):
    """Authentication or authorization error."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="AUTH_ERROR", **kwargs)


class RegistrationError(AIPError):
    """Error during agent registration."""
    
    def __init__(
        self,
        message: str = "Agent registration failed",
        *,
        agent_id: Optional[str] = None,
        handle: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="REGISTRATION_ERROR", **kwargs)
        self.agent_id = agent_id
        self.handle = handle
        if agent_id:
            self.details["agent_id"] = agent_id
        if handle:
            self.details["handle"] = handle


class ExecutionError(AIPError):
    """Error during task execution."""
    
    def __init__(
        self,
        message: str = "Task execution failed",
        *,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="EXECUTION_ERROR", **kwargs)
        self.task_id = task_id
        self.agent_id = agent_id
        self.run_id = run_id
        if task_id:
            self.details["task_id"] = task_id
        if agent_id:
            self.details["agent_id"] = agent_id
        if run_id:
            self.details["run_id"] = run_id


class PaymentError(AIPError):
    """Error related to payment processing."""
    
    def __init__(
        self,
        message: str = "Payment processing failed",
        *,
        amount: Optional[float] = None,
        payer: Optional[str] = None,
        receiver: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="PAYMENT_ERROR", **kwargs)
        self.amount = amount
        self.payer = payer
        self.receiver = receiver
        if amount:
            self.details["amount"] = amount
        if payer:
            self.details["payer"] = payer
        if receiver:
            self.details["receiver"] = receiver


class ValidationError(AIPError):
    """Error validating input data."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        *,
        field: Optional[str] = None,
        value: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="VALIDATION_ERROR", **kwargs)
        self.field = field
        self.value = value
        if field:
            self.details["field"] = field


class TimeoutError(AIPError):
    """Operation timed out."""
    
    def __init__(
        self,
        message: str = "Operation timed out",
        *,
        timeout_seconds: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="TIMEOUT_ERROR", **kwargs)
        self.timeout_seconds = timeout_seconds
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


class AgentNotFoundError(AIPError):
    """Requested agent was not found."""
    
    def __init__(
        self,
        message: str = "Agent not found",
        *,
        agent_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, code="AGENT_NOT_FOUND", **kwargs)
        self.agent_id = agent_id
        if agent_id:
            self.details["agent_id"] = agent_id

"""
Internal SDK Types and Base Classes

This module contains standalone implementations of core types that the SDK needs,
decoupled from the main unibase-aip platform. These are used internally by the SDK
and should not be imported directly by SDK users.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4


# ============================================================================
# Task Specifications
# ============================================================================

@dataclass
class TaskSpec:
    """
    Specification for a task to be executed by an agent.
    Standalone version used internally by the SDK.
    """
    task_id: str
    name: str
    description: str
    payload: Dict[str, Any] = field(default_factory=dict)
    assigned_agent: Optional[str] = None


# ============================================================================
# Agent Identity
# ============================================================================

@dataclass
class IdentityMetadata:
    """Metadata for an agent identity."""
    display_name: str
    capabilities: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


class ERC8004Identity:
    """
    Simplified ERC8004 identity implementation for SDK use.
    This is a standalone version that doesn't depend on blockchain storage.
    """

    def __init__(self, identity_id: str, handle: str, metadata: IdentityMetadata):
        self.identity_id = identity_id
        self.handle = handle
        self.metadata = metadata

    @classmethod
    def create(cls, handle: str, metadata: IdentityMetadata) -> "ERC8004Identity":
        """Create a new ERC8004 identity."""
        identity_id = f"erc8004:{handle}"
        return cls(identity_id, handle, metadata)

    def __repr__(self) -> str:
        return f"ERC8004Identity(id={self.identity_id}, handle={self.handle})"


# ============================================================================
# Skill Templates
# ============================================================================

@dataclass
class SkillIOField:
    """Field definition for skill input/output."""
    name: str
    field_type: str = "string"
    description: str = ""


class ClaudeSkillTemplate:
    """
    Template for defining agent skills.
    Standalone version for SDK use.
    """

    def __init__(
        self,
        name: str,
        description: str,
        inputs: Optional[List[SkillIOField]] = None,
        outputs: Optional[List[SkillIOField]] = None,
    ):
        self.name = name
        self.description = description
        self.inputs = inputs or []
        self.outputs = outputs or []

    def __repr__(self) -> str:
        return f"ClaudeSkillTemplate(name={self.name})"


# ============================================================================
# Agent Base Classes
# ============================================================================

@dataclass
class AgentCostModel:
    """Cost model for agent execution."""
    base_call_fee: float = 0.0
    per_agent_call_fee: float = 0.0


@dataclass
class AgentInvocationResult:
    """Result of an agent task invocation."""
    output: Dict[str, Any]
    summary: str
    used_tools: List[str] = field(default_factory=list)
    downstream_calls: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


@dataclass
class AgentExecutionContext:
    """
    Context provided to agents during task execution.
    Standalone version for SDK use.
    """

    # Callable for invoking other agents
    invoke_agent: Callable[[str, Any, str], Awaitable[AgentInvocationResult]]

    # Callable for emitting events
    emit_event: Callable[[Dict[str, Any]], None]

    # Callable for sending messages
    send_message: Callable[[Any], Awaitable[None]]

    # Callable for receiving messages
    receive_message: Callable[[Optional[str], Optional[float]], Awaitable[Any]]

    # Callable for reading from memory
    memory_read: Callable[[str], Dict[str, Any]]

    # Callable for writing to memory
    memory_write: Callable[[str, Dict[str, Any], str], None]


class Agent:
    """
    Base agent class.
    Standalone version for SDK use.
    """

    def __init__(
        self,
        identity: ERC8004Identity,
        skills: Optional[List[ClaudeSkillTemplate]] = None,
        cost_model: Optional[AgentCostModel] = None,
    ):
        self.identity = identity
        self.skills = skills or []
        self.cost_model = cost_model or AgentCostModel()

    @property
    def agent_id(self) -> str:
        """Get the agent's unique identifier."""
        return self.identity.identity_id

    async def perform_task(
        self,
        task: TaskSpec,
        context: AgentExecutionContext,
    ) -> AgentInvocationResult:
        """
        Execute a task. Should be overridden by subclasses.

        Args:
            task: The task to execute
            context: Execution context with utilities

        Returns:
            Result of the task execution
        """
        raise NotImplementedError("Subclasses must implement perform_task")

    def __repr__(self) -> str:
        return f"Agent(id={self.agent_id})"

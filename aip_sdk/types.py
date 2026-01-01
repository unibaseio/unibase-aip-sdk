"""SDK Type Definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
)
from enum import Enum



class RunStatus(Enum):
    """Status of a run execution in the AIP platform."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"




@dataclass
class Task:
    """Task specification for SDK use."""
    task_id: str
    name: str
    description: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    assigned_agent: Optional[str] = None

    @classmethod
    def from_domain(cls, task: Any) -> "Task":
        """Create Task from domain task object."""
        if isinstance(task, dict):
            return cls(
                task_id=task.get("task_id", ""),
                name=task.get("name", ""),
                description=task.get("description", ""),
                payload=task.get("payload", {}),
                assigned_agent=task.get("assigned_agent"),
            )
        return cls(
            task_id=getattr(task, "task_id", ""),
            name=getattr(task, "name", ""),
            description=getattr(task, "description", ""),
            payload=getattr(task, "payload", {}),
            assigned_agent=getattr(task, "assigned_agent", None),
        )


@dataclass
class SkillInput:
    """Definition of a skill input parameter."""
    name: str
    field_type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass
class SkillOutput:
    """Definition of a skill output parameter."""
    name: str
    field_type: str = "string"
    description: str = ""


@dataclass
class SkillConfig:
    """Configuration for an agent skill."""
    name: str
    description: str
    inputs: List[SkillInput] = field(default_factory=list)
    outputs: List[SkillOutput] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        return {
            "name": self.name,
            "description": self.description,
            "inputs": [
                {
                    "name": i.name,
                    "field_type": i.field_type,
                    "description": i.description,
                }
                for i in self.inputs
            ],
            "outputs": [
                {
                    "name": o.name,
                    "field_type": o.field_type,
                    "description": o.description,
                }
                for o in self.outputs
            ],
        }


@dataclass
class CostModel:
    """Agent cost model configuration.

    Unified cost model supporting various fee structures:
    - base_call_fee: Fixed fee per call
    - per_agent_call_fee: Fee for agent-to-agent calls (legacy, prefer base_call_fee)
    - per_use_fee: Fee per usage/invocation
    - per_write_fee: Fee for write operations
    - per_token_fee: Fee per token processed
    - custom_fees: Additional custom fee structures
    """
    base_call_fee: Optional[float] = None
    per_agent_call_fee: Optional[float] = None  # Legacy field
    per_use_fee: Optional[float] = None
    per_write_fee: Optional[float] = None
    per_token_fee: Optional[float] = None
    custom_fees: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"custom_fees": self.custom_fees}
        if self.base_call_fee is not None:
            result["base_call_fee"] = self.base_call_fee
        if self.per_agent_call_fee is not None:
            result["per_agent_call_fee"] = self.per_agent_call_fee
        if self.per_use_fee is not None:
            result["per_use_fee"] = self.per_use_fee
        if self.per_write_fee is not None:
            result["per_write_fee"] = self.per_write_fee
        if self.per_token_fee is not None:
            result["per_token_fee"] = self.per_token_fee
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostModel":
        """Create from dictionary."""
        return cls(
            base_call_fee=data.get("base_call_fee"),
            per_agent_call_fee=data.get("per_agent_call_fee"),
            per_use_fee=data.get("per_use_fee"),
            per_write_fee=data.get("per_write_fee"),
            per_token_fee=data.get("per_token_fee"),
            custom_fees=data.get("custom_fees", {}),
        )


@dataclass
class AgentConfig:
    """Configuration for an agent.

    Pricing is controlled via `cost_model`. The simplest usage is:
        AgentConfig(name="MyAgent", cost_model=CostModel(base_call_fee=0.05))

    This sets the price per call to $0.05. For more complex pricing, use
    additional CostModel fields like per_use_fee, per_token_fee, etc.
    """
    name: str
    description: str = ""
    handle: Optional[str] = None
    skills: List[SkillConfig] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    cost_model: CostModel = field(default_factory=CostModel)
    currency: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)
    endpoint_url: Optional[str] = None

    @property
    def price(self) -> float:
        """Get the primary price (base_call_fee from cost_model)."""
        return self.cost_model.base_call_fee or 0.001

    def to_registration_dict(self) -> Dict[str, Any]:
        """Convert to registration API format."""
        handle = self.handle or self.name.lower().replace(" ", "_")

        return {
            "handle": handle,
            "card": {
                "name": self.name,
                "description": self.description,
                "capabilities": self.capabilities,
            },
            "skills": [s.to_dict() for s in self.skills],
            "tasks": [
                {"name": s.name, "description": s.description}
                for s in self.skills
            ],
            "cost_model": self.cost_model.to_dict(),
            "price": {
                "amount": self.price,
                "currency": self.currency,
            },
            "metadata": self.metadata,
            "endpoint_url": self.endpoint_url,
        }


@dataclass
class TaskResult:
    """Result of a task execution."""
    output: Dict[str, Any]
    summary: str
    used_tools: List[str] = field(default_factory=list)
    downstream_calls: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    @classmethod
    def success_result(
        cls,
        output: Dict[str, Any],
        summary: str = "",
        used_tools: Optional[List[str]] = None,
    ) -> "TaskResult":
        """Create a successful result."""
        return cls(
            output=output,
            summary=summary or str(output),
            used_tools=used_tools or [],
            success=True,
        )

    @classmethod
    def error_result(cls, error: str) -> "TaskResult":
        """Create an error result."""
        return cls(
            output={"error": error},
            summary=error,
            success=False,
            error=error,
        )


@dataclass
class AgentContext:
    """Context provided to agent handlers during task execution."""
    invoke_agent: Callable[[str, Any, str], Awaitable[TaskResult]]
    emit_event: Callable[[Dict[str, Any]], None]
    send_message: Callable[[Any], Awaitable[None]]
    receive_message: Callable[[Optional[str], Optional[float]], Awaitable[Any]]
    memory_read: Callable[[str], Dict[str, Any]]
    memory_write: Callable[[str, Dict[str, Any], str], None]

    async def call_agent(
        self,
        agent_id: str,
        task_name: str,
        payload: Dict[str, Any],
        reason: str = "",
    ) -> TaskResult:
        """Call another agent with a task."""
        from uuid import uuid4
        task = Task(
            task_id=str(uuid4()),
            name=task_name,
            description=reason or f"Call to {agent_id}",
            payload=payload,
        )
        result = await self.invoke_agent(agent_id, task, reason)
        if hasattr(result, 'output'):
            return TaskResult(
                output=result.output,
                summary=getattr(result, 'summary', ''),
                used_tools=getattr(result, 'used_tools', []),
                downstream_calls=getattr(result, 'downstream_calls', []),
            )
        return result

    def log(self, event_type: str, **data: Any) -> None:
        """Log an event."""
        self.emit_event({"type": event_type, **data})

    async def read(self, scope: str) -> Dict[str, Any]:
        """Read from agent memory."""
        return self.memory_read(scope)

    async def write(
        self,
        scope: str,
        data: Dict[str, Any],
        description: str = "",
    ) -> None:
        """Write to agent memory."""
        self.memory_write(scope, data, description)

    @classmethod
    def from_execution_context(cls, ctx: Any) -> "AgentContext":
        """Create from domain AgentExecutionContext."""
        return cls(
            invoke_agent=ctx.invoke_agent,
            emit_event=ctx.emit_event,
            send_message=ctx.send_message,
            receive_message=ctx.receive_message,
            memory_read=ctx.memory_read,
            memory_write=ctx.memory_write,
        )

    @classmethod
    def from_a2a_factory(
        cls,
        factory: Any,
        run_id: str,
        caller_agent: str,
        *,
        emit_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        send_message: Optional[Callable[[Any], Awaitable[None]]] = None,
        receive_message: Optional[Callable[[Optional[str], Optional[float]], Awaitable[Any]]] = None,
        memory_read: Optional[Callable[[str], Dict[str, Any]]] = None,
        memory_write: Optional[Callable[[str, Dict[str, Any], str], None]] = None,
    ) -> "AgentContext":
        """Create AgentContext with A2A-based invoke_agent."""
        import json
        from a2a.types import Message, TaskState, Role

        try:
            from aip_sdk.agent.context import AIPContext, PaymentContextData
            from aip_sdk.agent.adapter import extract_text_from_message
        except ImportError:
            raise ImportError(
                "A2A module not available. Ensure aip_sdk.a2a is properly installed."
            )

        async def invoke_agent(
            target_agent: str,
            subtask: Any,
            reason: str = "",
        ) -> "TaskResult":
            """Invoke another agent via A2A."""
            # Convert subtask to A2A message
            if isinstance(subtask, dict):
                payload = subtask
            elif hasattr(subtask, "payload"):
                payload = subtask.payload
            else:
                payload = {"task": str(subtask)}

            # Create A2A message
            message = Message.user(json.dumps(payload))

            # Create AIP context
            aip_context = AIPContext(
                run_id=run_id,
                caller_agent=caller_agent,
                caller_chain=[],
                payment_context=PaymentContextData(
                    run_id=run_id,
                    caller=caller_agent,
                    actor=target_agent,
                    chain=[caller_agent],
                ),
            )

            try:
                # Send via A2A
                result_task = await factory.send_task(
                    agent_id=target_agent,
                    message=message,
                    aip_context=aip_context,
                )

                # Convert to TaskResult
                output = {}
                summary = ""

                # Get response from history (last agent message)
                for msg in reversed(result_task.history):
                    if msg.role == Role.AGENT:
                        text = extract_text_from_message(msg)
                        summary = text
                        try:
                            output = json.loads(text)
                        except json.JSONDecodeError:
                            output = {"response": text}
                        break

                # Check artifacts
                for artifact in result_task.artifacts:
                    for part in artifact.parts:
                        if hasattr(part, "text"):
                            if "artifact" not in output:
                                output["artifact"] = part.text
                        if hasattr(part, "data"):
                            if "data" not in output:
                                output["data"] = part.data

                # Determine success based on state
                success = result_task.status.state == TaskState.COMPLETED
                error = None
                if not success and result_task.status.message:
                    error = extract_text_from_message(result_task.status.message)

                return TaskResult(
                    output=output,
                    summary=summary,
                    used_tools=[],
                    downstream_calls=[],
                    success=success,
                    error=error,
                )

            except Exception as e:
                return TaskResult.error_result(str(e))

        return cls(
            invoke_agent=invoke_agent,
            emit_event=emit_event or (lambda event: None),
            send_message=send_message or (lambda msg: None),
            receive_message=receive_message or (lambda topic, timeout: None),
            memory_read=memory_read or (lambda scope: {}),
            memory_write=memory_write or (lambda scope, data, desc: None),
        )


@dataclass
class EventData:
    """Data from a streaming event."""
    event_type: str
    payload: Dict[str, Any]
    timestamp: Optional[str] = None
    run_id: Optional[str] = None
    
    @property
    def is_completed(self) -> bool:
        """Check if this event indicates completion."""
        return self.event_type in ("run.completed", "orchestrator.completed")
    
    @property
    def is_error(self) -> bool:
        """Check if this event indicates an error."""
        return self.event_type in ("run.failed", "orchestrator.error", "error")
    
    @property
    def message(self) -> Optional[str]:
        """Get event message if available."""
        return self.payload.get("message") or self.payload.get("summary")


@dataclass
class RunResult:
    """Result of running a task through the orchestrator."""
    run_id: str
    status: RunStatus
    result: Optional[Dict[str, Any]] = None
    events: List[EventData] = field(default_factory=list)
    error: Optional[str] = None
    payments: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == RunStatus.COMPLETED

    @property
    def output(self) -> Optional[Any]:
        """Get the main output from the result."""
        if self.result:
            return self.result.get("output") or self.result.get("result")
        return None


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    agent_id: str
    handle: str
    name: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    price: float = 0.0
    endpoint_url: Optional[str] = None
    on_chain: bool = False
    identity_address: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        """Create from API response."""
        card = data.get("card", {})
        return cls(
            agent_id=data.get("agent_id", ""),
            handle=data.get("handle", ""),
            name=card.get("name", data.get("name", "")),
            description=card.get("description", data.get("description", "")),
            capabilities=card.get("capabilities", []),
            skills=data.get("skills", []),
            price=data.get("price", {}).get("amount", 0.0) if isinstance(data.get("price"), dict) else 0.0,
            endpoint_url=data.get("endpoint_url"),
            on_chain=data.get("metadata", {}).get("onchain", False),
            identity_address=data.get("identity_address"),
        )


@dataclass
class PaginatedResponse:
    """Generic paginated response from the API."""
    items: List[Any]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        """Check if there are more items available."""
        return self.offset + self.limit < self.total

    @property
    def next_offset(self) -> Optional[int]:
        """Get offset for next page, or None if no more pages."""
        if self.has_more:
            return self.offset + self.limit
        return None


@dataclass
class UserInfo:
    """Information about a registered user."""
    user_id: str
    wallet_address: str
    email: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInfo":
        """Create from API response."""
        return cls(
            user_id=data["user_id"],
            wallet_address=data["wallet_address"],
            email=data.get("email"),
            created_at=data.get("created_at"),
        )


@dataclass
class PriceInfo:
    """Price information for an agent or resource."""
    identifier: str
    amount: float
    currency: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceInfo":
        """Create from API response."""
        return cls(
            identifier=data["identifier"],
            amount=data["amount"],
            currency=data.get("currency", "USD"),
            metadata=data.get("metadata", {}),
        )

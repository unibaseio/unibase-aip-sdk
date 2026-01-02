"""SDK Type Definitions."""

from __future__ import annotations

from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(Enum):
    """Status of a run execution in the AIP platform."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """Task specification for SDK use."""

    task_id: str
    name: str
    description: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    assigned_agent: Optional[str] = None

    @classmethod
    def from_domain(cls, task: Any) -> Task:
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


class SkillInput(BaseModel):
    """Definition of a skill input parameter."""

    name: str
    field_type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None


class SkillOutput(BaseModel):
    """Definition of a skill output parameter."""

    name: str
    field_type: str = "string"
    description: str = ""


class SkillConfig(BaseModel):
    """Configuration for an agent skill."""

    name: str
    description: str
    inputs: List[SkillInput] = Field(default_factory=list)
    outputs: List[SkillOutput] = Field(default_factory=list)

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


class CostModel(BaseModel):
    """Agent cost model configuration."""

    base_call_fee: Optional[float] = None
    per_agent_call_fee: Optional[float] = None
    per_use_fee: Optional[float] = None
    per_write_fee: Optional[float] = None
    per_token_fee: Optional[float] = None
    custom_fees: Dict[str, float] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = self.model_dump(exclude_none=True)
        result["custom_fees"] = self.custom_fees
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CostModel:
        """Create from dictionary."""
        return cls.model_validate(data)


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    name: str
    description: str = ""
    handle: Optional[str] = None
    skills: List[SkillConfig] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    cost_model: CostModel = Field(default_factory=CostModel)
    currency: str = "USD"
    metadata: Dict[str, Any] = Field(default_factory=dict)
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
                {"name": s.name, "description": s.description} for s in self.skills
            ],
            "cost_model": self.cost_model.to_dict(),
            "price": {
                "amount": self.price,
                "currency": self.currency,
            },
            "metadata": self.metadata,
            "endpoint_url": self.endpoint_url,
        }


class TaskResult(BaseModel):
    """Result of a task execution."""

    output: Dict[str, Any]
    summary: str
    used_tools: List[str] = Field(default_factory=list)
    downstream_calls: List[str] = Field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    @classmethod
    def success_result(
        cls,
        output: Dict[str, Any],
        summary: str = "",
        used_tools: Optional[List[str]] = None,
    ) -> TaskResult:
        """Create a successful result."""
        return cls(
            output=output,
            summary=summary or str(output),
            used_tools=used_tools or [],
            success=True,
        )

    @classmethod
    def error_result(cls, error: str) -> TaskResult:
        """Create an error result."""
        return cls(
            output={"error": error},
            summary=error,
            success=False,
            error=error,
        )


class AgentContext:
    """Context provided to agent handlers during task execution.

    Note: This remains a regular class (not Pydantic) because it contains
    callable fields that are not serializable.
    """

    def __init__(
        self,
        invoke_agent: Callable[[str, Any, str], Awaitable[TaskResult]],
        emit_event: Callable[[Dict[str, Any]], None],
        send_message: Callable[[Any], Awaitable[None]],
        receive_message: Callable[[Optional[str], Optional[float]], Awaitable[Any]],
        memory_read: Callable[[str], Dict[str, Any]],
        memory_write: Callable[[str, Dict[str, Any], str], None],
    ):
        self.invoke_agent = invoke_agent
        self.emit_event = emit_event
        self.send_message = send_message
        self.receive_message = receive_message
        self.memory_read = memory_read
        self.memory_write = memory_write

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
        if hasattr(result, "output"):
            return TaskResult(
                output=result.output,
                summary=getattr(result, "summary", ""),
                used_tools=getattr(result, "used_tools", []),
                downstream_calls=getattr(result, "downstream_calls", []),
            )
        return result

    async def call_agent_with_intent(
        self,
        agent_id: str,
        intent: str,
        *,
        structured_data: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ) -> TaskResult:
        """Call another agent with an AgentMessage-style intent."""
        payload: Dict[str, Any] = {"user_request": intent}
        if structured_data:
            payload["structured_data"] = structured_data

        return await self.call_agent(
            agent_id=agent_id,
            task_name="agent_request",
            payload=payload,
            reason=reason,
        )

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
    def from_execution_context(cls, ctx: Any) -> AgentContext:
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
        receive_message: Optional[
            Callable[[Optional[str], Optional[float]], Awaitable[Any]]
        ] = None,
        memory_read: Optional[Callable[[str], Dict[str, Any]]] = None,
        memory_write: Optional[Callable[[str, Dict[str, Any], str], None]] = None,
    ) -> AgentContext:
        """Create AgentContext with A2A-based invoke_agent."""
        import json

        from a2a.types import Message, Role, TaskState

        try:
            from aip_sdk.agent.adapter import extract_text_from_message
            from aip_sdk.agent.context import AIPContext, PaymentContextData
        except ImportError:
            raise ImportError(
                "A2A module not available. Ensure aip_sdk.a2a is properly installed."
            )

        async def invoke_agent(
            target_agent: str,
            subtask: Any,
            reason: str = "",
        ) -> TaskResult:
            """Invoke another agent via A2A."""
            if isinstance(subtask, dict):
                payload = subtask
            elif hasattr(subtask, "payload"):
                payload = subtask.payload
            else:
                payload = {"task": str(subtask)}

            message = Message.user(json.dumps(payload))

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
                result_task = await factory.send_task(
                    agent_id=target_agent,
                    message=message,
                    aip_context=aip_context,
                )

                output = {}
                summary = ""

                for msg in reversed(result_task.history):
                    if msg.role == Role.AGENT:
                        text = extract_text_from_message(msg)
                        summary = text
                        try:
                            output = json.loads(text)
                        except json.JSONDecodeError:
                            output = {"response": text}
                        break

                for artifact in result_task.artifacts:
                    for part in artifact.parts:
                        if hasattr(part, "text"):
                            if "artifact" not in output:
                                output["artifact"] = part.text
                        if hasattr(part, "data"):
                            if "data" not in output:
                                output["data"] = part.data

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


class EventData(BaseModel):
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


class RunResult(BaseModel):
    """Result of running a task through the orchestrator."""

    run_id: str
    status: RunStatus
    result: Optional[Dict[str, Any]] = None
    events: List[EventData] = Field(default_factory=list)
    error: Optional[str] = None
    payments: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(use_enum_values=True)

    @property
    def success(self) -> bool:
        return self.status == RunStatus.COMPLETED

    @property
    def output(self) -> Optional[Any]:
        """Get the main output from the result."""
        if self.result:
            return self.result.get("output") or self.result.get("result")
        return None


class AgentInfo(BaseModel):
    """Information about a registered agent."""

    agent_id: str
    handle: str
    name: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    price: float = 0.0
    endpoint_url: Optional[str] = None
    on_chain: bool = False
    identity_address: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentInfo:
        """Create from API response."""
        card = data.get("card", {})
        price_data = data.get("price")
        price_amount = 0.0
        if isinstance(price_data, dict):
            price_amount = price_data.get("amount", 0.0)

        return cls(
            agent_id=data.get("agent_id", ""),
            handle=data.get("handle", ""),
            name=card.get("name", data.get("name", "")),
            description=card.get("description", data.get("description", "")),
            capabilities=card.get("capabilities", []),
            skills=data.get("skills", []),
            price=price_amount,
            endpoint_url=data.get("endpoint_url"),
            on_chain=data.get("metadata", {}).get("onchain", False),
            identity_address=data.get("identity_address"),
        )


class PaginatedResponse(BaseModel):
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


class UserInfo(BaseModel):
    """Information about a registered user."""

    user_id: str
    wallet_address: str
    email: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserInfo:
        """Create from API response."""
        return cls.model_validate(data)


class PriceInfo(BaseModel):
    """Price information for an agent or resource."""

    identifier: str
    amount: float
    currency: str = "USD"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PriceInfo:
        """Create from API response."""
        return cls.model_validate(data)


# =============================================================================
# Agent Communication Types
# =============================================================================


class MessageContext(BaseModel):
    """Context provided by AIP platform for agent communication."""

    run_id: str = ""
    caller_id: str = ""
    conversation_id: Optional[str] = None
    payment_authorized: bool = True
    caller_chain: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MessageContext:
        """Create from dictionary."""
        return cls.model_validate(data)


class RoutingHints(BaseModel):
    """Optional hints from the routing layer."""

    detected_category: Optional[str] = None
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    suggested_task: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RoutingHints:
        """Create from dictionary."""
        return cls.model_validate(data)


class AgentMessage(BaseModel):
    """Universal message format for agent communication."""

    intent: str
    context: MessageContext
    hints: Optional[RoutingHints] = None
    structured_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "intent": self.intent,
            "context": self.context.to_dict(),
        }
        if self.hints:
            result["hints"] = self.hints.to_dict()
        if self.structured_data:
            result["structured_data"] = self.structured_data
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentMessage:
        """Create from dictionary."""
        context_data = data.get("context", {})
        hints_data = data.get("hints")

        return cls(
            intent=data.get("intent", ""),
            context=MessageContext.from_dict(context_data),
            hints=RoutingHints.from_dict(hints_data) if hints_data else None,
            structured_data=data.get("structured_data"),
        )

    def get_intent_as_json(self) -> Optional[Dict[str, Any]]:
        """Try to parse intent as JSON, return None if not valid JSON."""
        import json

        try:
            return json.loads(self.intent)
        except (json.JSONDecodeError, TypeError):
            return None

    @classmethod
    def create(
        cls,
        intent: str,
        *,
        run_id: str,
        caller_id: str,
        conversation_id: Optional[str] = None,
        hints: Optional[RoutingHints] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Convenience factory to create an AgentMessage."""
        return cls(
            intent=intent,
            context=MessageContext(
                run_id=run_id,
                caller_id=caller_id,
                conversation_id=conversation_id,
                metadata=metadata or {},
            ),
            hints=hints,
        )

    @classmethod
    def from_a2a_message(cls, message: Any) -> AgentMessage:
        """Parse an A2A Message into AgentMessage format."""
        import json

        text_parts = []
        if hasattr(message, "parts"):
            for part in message.parts:
                if hasattr(part, "text"):
                    text_parts.append(part.text)
        text = " ".join(text_parts)

        try:
            data = json.loads(text)

            if "intent" in data and "context" in data:
                return cls.from_dict(data)

            if "task" in data:
                task_data = data["task"]
                payload = task_data.get("payload", {})
                intent = payload.get("intent") or task_data.get("description", "")
                context_data = payload.get("context", {})
                if not context_data:
                    context_data = {
                        "run_id": task_data.get("task_id", ""),
                        "caller_id": "unknown",
                    }

                return cls(
                    intent=intent,
                    context=MessageContext.from_dict(context_data),
                    hints=RoutingHints.from_dict(payload.get("hints", {}))
                    if payload.get("hints")
                    else None,
                    structured_data=payload.get("structured_data"),
                )

            return cls(
                intent=text,
                context=MessageContext(),
                structured_data=data,
            )

        except json.JSONDecodeError:
            return cls(
                intent=text,
                context=MessageContext(),
            )


class AgentResponse(BaseModel):
    """Standard response format from agents."""

    content: str
    data: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentResponse:
        """Create from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def success_response(
        cls,
        content: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Create a successful response."""
        return cls(content=content, data=data or {}, success=True)

    @classmethod
    def error_response(cls, error: str) -> AgentResponse:
        """Create an error response."""
        return cls(content=error, success=False, error=error)

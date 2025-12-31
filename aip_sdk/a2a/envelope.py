"""AIP Context Envelope for A2A Messages.

This module provides the AIPContext class which embeds AIP system context
(payment tracking, event bus, memory scope) into A2A messages via metadata.

This allows A2A messages to carry AIP-specific information without breaking
the standard A2A protocol.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from unibase_agent_sdk.a2a.types import Message


@dataclass
class PaymentContextData:
    """Serializable payment context data for embedding in A2A messages."""
    run_id: str
    caller: str
    actor: str
    chain: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaymentContextData":
        return cls(**data)


@dataclass
class AIPContext:
    """AIP system context embedded in A2A message metadata.

    This context travels with A2A messages to enable:
    - Payment tracking across agent calls
    - Event bus correlation
    - Memory scope isolation
    - Call chain tracing

    Attributes:
        run_id: Unique identifier for the entire run/session
        caller_agent: Agent that initiated this call
        caller_chain: Full chain of agents in the call stack
        payment_context: Payment tracking information
        memory_scope: Scope identifier for memory isolation
        event_bus_id: Event bus identifier for event correlation
        metadata: Additional custom metadata
    """
    run_id: str
    caller_agent: str
    caller_chain: List[str] = field(default_factory=list)
    payment_context: Optional[PaymentContextData] = None
    memory_scope: Optional[str] = None
    event_bus_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for embedding in A2A metadata."""
        result = {
            "run_id": self.run_id,
            "caller_agent": self.caller_agent,
            "caller_chain": self.caller_chain,
        }
        if self.payment_context:
            result["payment_context"] = self.payment_context.to_dict()
        if self.memory_scope:
            result["memory_scope"] = self.memory_scope
        if self.event_bus_id:
            result["event_bus_id"] = self.event_bus_id
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIPContext":
        """Deserialize from dictionary."""
        payment_data = data.get("payment_context")
        return cls(
            run_id=data["run_id"],
            caller_agent=data["caller_agent"],
            caller_chain=data.get("caller_chain", []),
            payment_context=PaymentContextData.from_dict(payment_data) if payment_data else None,
            memory_scope=data.get("memory_scope"),
            event_bus_id=data.get("event_bus_id"),
            metadata=data.get("metadata", {}),
        )

    def spawn_child(self, target_agent: str) -> "AIPContext":
        """Create a child context for delegating to another agent.

        This maintains the call chain and updates payment tracking.

        Args:
            target_agent: The agent being called

        Returns:
            New AIPContext with updated call chain
        """
        new_chain = self.caller_chain + [self.caller_agent]

        child_payment = None
        if self.payment_context:
            child_payment = PaymentContextData(
                run_id=self.payment_context.run_id,
                caller=self.caller_agent,
                actor=target_agent,
                chain=new_chain,
            )

        return AIPContext(
            run_id=self.run_id,
            caller_agent=self.caller_agent,
            caller_chain=new_chain,
            payment_context=child_payment,
            memory_scope=self.memory_scope,
            event_bus_id=self.event_bus_id,
            metadata=self.metadata.copy(),
        )


# Metadata key for AIP context in A2A messages
AIP_CONTEXT_KEY = "aip_context"


def wrap_message(
    message: Message,
    aip_context: AIPContext,
) -> Message:
    """Embed AIP context into an A2A message's metadata.

    This wraps the message with AIP-specific context while preserving
    any existing metadata.

    Args:
        message: The A2A message to wrap
        aip_context: AIP context to embed

    Returns:
        New Message with AIP context in metadata
    """
    existing_metadata = message.metadata or {}
    new_metadata = {
        **existing_metadata,
        AIP_CONTEXT_KEY: aip_context.to_dict(),
    }

    return Message(
        role=message.role,
        parts=message.parts,
        metadata=new_metadata,
    )


def unwrap_message(message: Message) -> Tuple[Message, Optional[AIPContext]]:
    """Extract AIP context from an A2A message.

    Args:
        message: The A2A message to unwrap

    Returns:
        Tuple of (message without AIP context, extracted AIPContext or None)
    """
    if not message.metadata:
        return message, None

    metadata = message.metadata.copy()
    aip_data = metadata.pop(AIP_CONTEXT_KEY, None)

    clean_message = Message(
        role=message.role,
        parts=message.parts,
        metadata=metadata if metadata else None,
    )

    aip_context = AIPContext.from_dict(aip_data) if aip_data else None

    return clean_message, aip_context


def extract_aip_context(message: Message) -> Optional[AIPContext]:
    """Extract AIP context from message without modifying it.

    Args:
        message: The A2A message

    Returns:
        AIPContext if present, None otherwise
    """
    if not message.metadata:
        return None

    aip_data = message.metadata.get(AIP_CONTEXT_KEY)
    return AIPContext.from_dict(aip_data) if aip_data else None

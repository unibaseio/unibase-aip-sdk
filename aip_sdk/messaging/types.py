"""AIP-specific types for A2A message extensions."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class PaymentEvent(BaseModel):
    """Payment event that occurred during agent execution."""

    type: str = "payment"
    agent_id: str
    amount: float
    currency: str = "USD"
    protocol: str = "X402"
    timestamp: str
    status: str = "settled"  # settled, pending, failed
    transaction_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PaymentEvent:
        """Deserialize from dict."""
        return cls.model_validate(data)


class RoutingHints(BaseModel):
    """Hints for routing messages to appropriate agents."""

    detected_category: Optional[str] = None
    suggested_agents: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RoutingHints:
        """Deserialize from dict."""
        return cls.model_validate(data)


class AIPMetadata(BaseModel):
    """AIP platform metadata embedded in A2A messages.

    This is stored in message.metadata['_aip'] and contains all
    AIP-specific context needed for orchestration, payment, and routing.
    """

    # === Execution Context ===
    run_id: str = Field(description="Unique ID for this execution run")
    caller_id: str = Field(description="Agent or user that initiated this request")
    caller_chain: List[str] = Field(
        default_factory=list,
        description="Full chain of callers (for nested agent calls)"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="ID for multi-turn conversations"
    )

    # === Payment Tracking ===
    payment_authorized: bool = Field(
        default=True,
        description="Whether payment is authorized for this request"
    )
    payment_events: List[PaymentEvent] = Field(
        default_factory=list,
        description="Payment events that occurred during execution"
    )

    # === Routing ===
    routing_hints: Optional[RoutingHints] = Field(
        default=None,
        description="Hints for agent selection and routing"
    )
    target_agent: Optional[str] = Field(
        default=None,
        description="Specific agent to route to (bypasses routing)"
    )

    # === Memory & State ===
    memory_scope: Optional[str] = Field(
        default=None,
        description="Memory scope for this execution"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for stateful agents"
    )

    # === Extensible ===
    custom: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata for extensions"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for embedding in A2A metadata."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AIPMetadata:
        """Deserialize from dict."""
        # Handle payment_events conversion
        if "payment_events" in data and isinstance(data["payment_events"], list):
            data["payment_events"] = [
                PaymentEvent.model_validate(e) if isinstance(e, dict) else e
                for e in data["payment_events"]
            ]

        # Handle routing_hints conversion
        if "routing_hints" in data and isinstance(data["routing_hints"], dict):
            data["routing_hints"] = RoutingHints.model_validate(data["routing_hints"])

        return cls.model_validate(data)

    def spawn_child(self, target_agent: str, new_run_id: Optional[str] = None) -> AIPMetadata:
        """Create child metadata for nested agent calls.

        Args:
            target_agent: The agent being called
            new_run_id: Optional new run ID (defaults to parent run_id)

        Returns:
            New AIPMetadata with updated caller chain
        """
        # Build new caller chain
        new_chain = self.caller_chain.copy()
        if not new_chain or new_chain[-1] != self.caller_id:
            new_chain.append(self.caller_id)

        return AIPMetadata(
            run_id=new_run_id or self.run_id,
            caller_id=target_agent,
            caller_chain=new_chain,
            conversation_id=self.conversation_id,
            payment_authorized=self.payment_authorized,
            payment_events=[],  # Fresh events for child
            routing_hints=None,  # Don't inherit routing
            target_agent=target_agent,
            memory_scope=self.memory_scope,
            session_id=self.session_id,
            custom=self.custom.copy(),
        )


# Metadata key for AIP extensions in A2A message.metadata
AIP_METADATA_KEY = "_aip"

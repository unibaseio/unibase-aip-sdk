"""Helper functions for working with A2A Messages + AIP extensions."""

from typing import Dict, Any, Optional, List
import uuid
import json
from datetime import datetime

from a2a.types import Message, TextPart, Role, DataPart
from a2a.utils.message import get_message_text

from .types import AIPMetadata, AIP_METADATA_KEY, PaymentEvent, RoutingHints


class MessageHelpers:
    """Utilities for creating and manipulating A2A Messages with AIP metadata."""

    # ========================================================================
    # Message Creation
    # ========================================================================

    @staticmethod
    def create_user_message(
        text: str,
        *,
        run_id: str,
        caller_id: str,
        caller_chain: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
        routing_hints: Optional[RoutingHints] = None,
        target_agent: Optional[str] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
    ) -> Message:
        """Create a user message with AIP metadata.

        This is the standard format for all internal AIP messages.

        Args:
            text: The user's request text
            run_id: Unique execution run ID
            caller_id: ID of the caller (user or agent)
            caller_chain: Full chain of callers (for nested calls)
            conversation_id: Optional conversation ID for multi-turn
            routing_hints: Optional routing hints
            target_agent: Optional specific agent to route to
            structured_data: Optional structured data (added to custom metadata)
            message_id: Optional message ID (auto-generated if not provided)

        Returns:
            A2A Message with AIP metadata
        """
        # Create AIP metadata
        aip_meta = AIPMetadata(
            run_id=run_id,
            caller_id=caller_id,
            caller_chain=caller_chain or [],
            conversation_id=conversation_id,
            routing_hints=routing_hints,
            target_agent=target_agent,
            custom=structured_data or {},
        )

        # Build message parts
        parts = [TextPart(text=text)]

        # If structured data provided, optionally add as data part
        if structured_data:
            try:
                parts.append(DataPart(data=structured_data))
            except Exception:
                # DataPart might not be available in all A2A versions
                pass

        return Message(
            message_id=message_id or str(uuid.uuid4()),
            role=Role.user,
            parts=parts,
            metadata={AIP_METADATA_KEY: aip_meta.to_dict()},
        )

    @staticmethod
    def create_agent_message(
        text: str,
        *,
        success: bool = True,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        aip_metadata: Optional[AIPMetadata] = None,
        message_id: Optional[str] = None,
    ) -> Message:
        """Create an agent response message.

        Args:
            text: The agent's response text
            success: Whether the operation succeeded
            output: Optional structured output data
            error: Optional error message if success=False
            aip_metadata: Optional AIP metadata to include
            message_id: Optional message ID

        Returns:
            A2A Message with agent response
        """
        # Build standard metadata
        metadata: Dict[str, Any] = {
            "success": success,
        }

        if error:
            metadata["error"] = error

        if output:
            metadata["output"] = output

        # Add AIP metadata if provided
        if aip_metadata:
            metadata[AIP_METADATA_KEY] = aip_metadata.to_dict()

        # Build parts
        parts = [TextPart(text=text)]
        if output:
            try:
                parts.append(DataPart(data=output))
            except Exception:
                # DataPart might not be available
                pass

        return Message(
            message_id=message_id or str(uuid.uuid4()),
            role=Role.agent,
            parts=parts,
            metadata=metadata,
        )

    # ========================================================================
    # Metadata Access
    # ========================================================================

    @staticmethod
    def get_aip_metadata(message: Message) -> Optional[AIPMetadata]:
        """Extract AIP metadata from A2A message.

        Args:
            message: A2A message

        Returns:
            AIPMetadata if present, None otherwise
        """
        if not message.metadata:
            return None

        aip_data = message.metadata.get(AIP_METADATA_KEY)
        if not aip_data:
            return None

        try:
            return AIPMetadata.from_dict(aip_data)
        except Exception as e:
            # Log warning but don't fail
            import logging
            logging.warning(f"Failed to parse AIP metadata: {e}")
            return None

    @staticmethod
    def set_aip_metadata(
        message: Message,
        aip_metadata: AIPMetadata,
    ) -> Message:
        """Set AIP metadata on a message (returns new message).

        Args:
            message: Original message
            aip_metadata: AIP metadata to set

        Returns:
            New message with updated metadata
        """
        new_metadata = {**(message.metadata or {})}
        new_metadata[AIP_METADATA_KEY] = aip_metadata.to_dict()

        return Message(
            message_id=message.message_id,
            role=message.role,
            parts=message.parts,
            metadata=new_metadata,
        )

    @staticmethod
    def update_aip_metadata(
        message: Message,
        **updates: Any,
    ) -> Message:
        """Update specific fields in AIP metadata.

        Args:
            message: Original message
            **updates: Fields to update (e.g., run_id="new-id")

        Returns:
            New message with updated metadata
        """
        current = MessageHelpers.get_aip_metadata(message)
        if not current:
            # Create new metadata if none exists
            current = AIPMetadata(
                run_id=updates.get("run_id", ""),
                caller_id=updates.get("caller_id", ""),
            )

        # Update fields
        for key, value in updates.items():
            if hasattr(current, key):
                setattr(current, key, value)

        return MessageHelpers.set_aip_metadata(message, current)

    # ========================================================================
    # Content Access
    # ========================================================================

    @staticmethod
    def get_text(message: Message) -> str:
        """Extract text content from message.

        Args:
            message: A2A message

        Returns:
            Extracted text
        """
        return get_message_text(message)

    @staticmethod
    def get_structured_data(message: Message) -> Optional[Dict[str, Any]]:
        """Extract structured data from message.

        Checks:
        1. DataPart in message.parts
        2. metadata.output
        3. AIP metadata custom field

        Args:
            message: A2A message

        Returns:
            Structured data if present
        """
        # Check parts for DataPart
        for part in message.parts:
            if hasattr(part, "data") and part.data:
                return part.data

        # Check metadata.output
        if message.metadata and "output" in message.metadata:
            return message.metadata["output"]

        # Check AIP custom metadata
        aip_meta = MessageHelpers.get_aip_metadata(message)
        if aip_meta and aip_meta.custom:
            return aip_meta.custom

        return None

    # ========================================================================
    # Payment Events
    # ========================================================================

    @staticmethod
    def add_payment_event(
        message: Message,
        agent_id: str,
        amount: float,
        currency: str = "USD",
        status: str = "settled",
        transaction_id: Optional[str] = None,
        **extra_metadata: Any,
    ) -> Message:
        """Add a payment event to message metadata.

        Args:
            message: Original message
            agent_id: Agent that charged
            amount: Payment amount
            currency: Currency code
            status: Payment status
            transaction_id: Optional blockchain transaction ID
            **extra_metadata: Additional payment metadata

        Returns:
            New message with payment event added
        """
        aip_meta = MessageHelpers.get_aip_metadata(message) or AIPMetadata(
            run_id="", caller_id=""
        )

        # Create payment event
        payment_event = PaymentEvent(
            agent_id=agent_id,
            amount=amount,
            currency=currency,
            timestamp=datetime.now().isoformat(),
            status=status,
            transaction_id=transaction_id,
            metadata=extra_metadata,
        )

        # Add to metadata
        aip_meta.payment_events.append(payment_event)

        return MessageHelpers.set_aip_metadata(message, aip_meta)

    @staticmethod
    def get_payment_events(message: Message) -> List[PaymentEvent]:
        """Get all payment events from message.

        Args:
            message: A2A message

        Returns:
            List of payment events
        """
        aip_meta = MessageHelpers.get_aip_metadata(message)
        return aip_meta.payment_events if aip_meta else []

    @staticmethod
    def get_total_cost(message: Message, currency: str = "USD") -> float:
        """Calculate total cost from payment events.

        Args:
            message: A2A message
            currency: Currency to filter by

        Returns:
            Total cost in specified currency
        """
        events = MessageHelpers.get_payment_events(message)
        return sum(
            e.amount for e in events
            if e.currency == currency and e.status == "settled"
        )

    # ========================================================================
    # Routing
    # ========================================================================

    @staticmethod
    def get_target_agent(message: Message) -> Optional[str]:
        """Get target agent from message metadata.

        Args:
            message: A2A message

        Returns:
            Target agent ID if specified
        """
        aip_meta = MessageHelpers.get_aip_metadata(message)
        return aip_meta.target_agent if aip_meta else None

    @staticmethod
    def set_routing_hints(
        message: Message,
        hints: RoutingHints,
    ) -> Message:
        """Set routing hints on message.

        Args:
            message: Original message
            hints: Routing hints

        Returns:
            New message with routing hints
        """
        return MessageHelpers.update_aip_metadata(
            message,
            routing_hints=hints,
        )

    # ========================================================================
    # Execution Context
    # ========================================================================

    @staticmethod
    def spawn_child_message(
        parent_message: Message,
        child_text: str,
        target_agent: str,
        new_run_id: Optional[str] = None,
    ) -> Message:
        """Create a child message for nested agent calls.

        This preserves the caller chain and creates proper context
        for inter-agent communication.

        Args:
            parent_message: The parent message
            child_text: Text for the child message
            target_agent: Agent to call
            new_run_id: Optional new run ID

        Returns:
            New message with proper child context
        """
        parent_meta = MessageHelpers.get_aip_metadata(parent_message)
        if not parent_meta:
            # No parent metadata, create fresh
            return MessageHelpers.create_user_message(
                text=child_text,
                run_id=new_run_id or str(uuid.uuid4()),
                caller_id="unknown",
                target_agent=target_agent,
            )

        # Spawn child metadata
        child_meta = parent_meta.spawn_child(
            target_agent=target_agent,
            new_run_id=new_run_id,
        )

        return Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[TextPart(text=child_text)],
            metadata={AIP_METADATA_KEY: child_meta.to_dict()},
        )


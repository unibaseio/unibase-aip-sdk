"""AIP Agent Development SDK.

This module provides tools for building agents:
- AIPContext: Context for agent execution with tracing
- A2AAgentAdapter: Adapts existing agents to A2A protocol
- ExternalAgentClient: Base class for Pull-mode agents
"""

from aip_sdk.agent.context import (
    AIPContext,
    PaymentContextData,
    wrap_message,
    unwrap_message,
    extract_aip_context,
    AIP_CONTEXT_KEY,
)
from aip_sdk.agent.adapter import (
    A2AAgentAdapter,
    adapt_agent,
    extract_text_from_message,
    extract_payload_from_message,
    parse_agent_message,
    task_result_to_message,
    agent_config_to_card,
)
from aip_sdk.agent.external import (
    ExternalAgentClient,
    CalculatorAgent,
    EchoAgent,
)

__all__ = [
    # Context
    "AIPContext",
    "PaymentContextData",
    "wrap_message",
    "unwrap_message",
    "extract_aip_context",
    "AIP_CONTEXT_KEY",
    # Adapter
    "A2AAgentAdapter",
    "adapt_agent",
    "extract_text_from_message",
    "extract_payload_from_message",
    "parse_agent_message",
    "task_result_to_message",
    "agent_config_to_card",
    # External agent (Pull mode)
    "ExternalAgentClient",
    "CalculatorAgent",
    "EchoAgent",
]

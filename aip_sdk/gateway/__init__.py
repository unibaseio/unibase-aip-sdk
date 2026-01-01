"""AIP Gateway SDK - Clients for interacting with the Gateway.

This module provides:
- GatewayClient: For registering agents and managing gateway routes
- GatewayA2AClient: For A2A communication through the gateway
- A2AClientInterface: Abstract interface for A2A clients
"""

from aip_sdk.gateway.client import (
    GatewayClient,
    SyncGatewayClient,
)
from aip_sdk.gateway.a2a_client import (
    GatewayA2AClient,
    GatewayError,
    TaskTimeoutError,
)
from aip_sdk.gateway.interface import (
    A2AClientInterface,
    TaskHandler,
    AgentNotFoundError,
)

__all__ = [
    # Gateway management
    "GatewayClient",
    "SyncGatewayClient",
    # A2A communication
    "GatewayA2AClient",
    "GatewayError",
    "TaskTimeoutError",
    # Interface
    "A2AClientInterface",
    "TaskHandler",
    "AgentNotFoundError",
]

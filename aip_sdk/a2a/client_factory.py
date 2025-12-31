"""A2A Client Factory - Unified Client Creation and Routing.

This factory provides a single entry point for creating A2A clients,
automatically routing requests to the appropriate transport:
- LocalA2AClient for in-process agents
- HttpA2AClient for direct HTTP connections
- GatewayA2AClient for gateway-mediated connections

The factory maintains a registry of local agents and discovered remote
agents, enabling transparent routing regardless of agent location.
"""

from typing import AsyncGenerator, Dict, Optional, Union
import logging

from unibase_agent_sdk.a2a.types import (
    Task,
    Message,
    AgentCard,
    StreamResponse,
)

from aip_sdk.a2a.interface import A2AClientInterface, TaskHandler
from aip_sdk.a2a.envelope import AIPContext
from aip_sdk.a2a.local_client import LocalA2AClient
from aip_sdk.a2a.http_client import HttpA2AClient
from aip_sdk.a2a.gateway_client import GatewayA2AClient
from aip_sdk.a2a.registry import LocalAgentRegistry

logger = logging.getLogger(__name__)


class A2AClientFactory(A2AClientInterface):
    """Factory for A2A clients with automatic routing.

    This factory implements A2AClientInterface directly, routing calls
    to the appropriate underlying client based on agent location.

    Routing Logic:
    1. Check if agent is registered locally -> LocalA2AClient
    2. Check if agent has known endpoint -> HttpA2AClient
    3. Check if gateway is configured -> GatewayA2AClient
    4. Raise AgentNotFoundError

    Features:
    - Automatic client selection based on agent location
    - Local agent registration and lookup
    - Remote agent endpoint caching
    - Gateway fallback for unknown agents
    - Unified interface for all agent communication

    Example:
        factory = A2AClientFactory()

        # Register a local agent
        factory.register_local_agent(
            agent_id="calculator",
            task_handler=calculator_handler,
            agent_card=calculator_card,
        )

        # Send task - automatically routes to local client
        message = Message.user("What is 2+2?")
        task = await factory.send_task("calculator", message)

        # Or to a remote agent - routes through gateway
        task = await factory.send_task("remote-agent", message)
    """

    def __init__(
        self,
        *,
        gateway_url: Optional[str] = None,
        gateway_mode: str = "push",
        default_timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize the A2A client factory.

        Args:
            gateway_url: Optional gateway URL for remote agents
            gateway_mode: Gateway mode ("push" or "pull")
            default_timeout: Default request timeout in seconds
            headers: Default headers for HTTP requests
        """
        self._gateway_url = gateway_url
        self._gateway_mode = gateway_mode
        self._default_timeout = default_timeout
        self._headers = headers or {}

        # Registry for local agents
        self._registry = LocalAgentRegistry()
        self._registry.set_a2a_client_factory(self)

        # Cached clients
        self._local_client: Optional[LocalA2AClient] = None
        self._gateway_client: Optional[GatewayA2AClient] = None
        self._http_clients: Dict[str, HttpA2AClient] = {}

    @property
    def registry(self) -> LocalAgentRegistry:
        """Get the local agent registry."""
        return self._registry

    @property
    def gateway_url(self) -> Optional[str]:
        """Get the configured gateway URL."""
        return self._gateway_url

    def set_gateway(self, gateway_url: str, mode: str = "push") -> None:
        """Configure the gateway for remote agents.

        Args:
            gateway_url: Gateway URL
            mode: Gateway mode ("push" or "pull")
        """
        self._gateway_url = gateway_url
        self._gateway_mode = mode
        # Reset gateway client to pick up new config
        self._gateway_client = None

    # Local agent management

    def register_local_agent(
        self,
        agent_id: str,
        task_handler: TaskHandler,
        agent_card: AgentCard,
        *,
        endpoint_url: Optional[str] = None,
        agent_instance: Optional[object] = None,
    ) -> None:
        """Register a local agent.

        Args:
            agent_id: Unique agent identifier
            task_handler: A2A TaskHandler for this agent
            agent_card: Agent capabilities description
            endpoint_url: Optional HTTP endpoint if also exposed remotely
            agent_instance: Optional reference to Agent object
        """
        self._registry.register_local(
            agent_id=agent_id,
            task_handler=task_handler,
            agent_card=agent_card,
            agent_instance=agent_instance,
            endpoint_url=endpoint_url,
        )
        logger.info(f"Registered local agent: {agent_id}")

    def unregister_local_agent(self, agent_id: str) -> bool:
        """Unregister a local agent.

        Args:
            agent_id: Agent to unregister

        Returns:
            True if agent was found and removed
        """
        return self._registry.unregister_local(agent_id)

    def is_local(self, agent_id: str) -> bool:
        """Check if an agent is registered locally.

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent is local
        """
        return self._registry.is_local(agent_id)

    # Remote agent management

    def register_remote_agent(
        self,
        agent_id: str,
        endpoint_url: str,
        agent_card: Optional[AgentCard] = None,
    ) -> None:
        """Register a known remote agent endpoint.

        Args:
            agent_id: Agent identifier
            endpoint_url: HTTP endpoint URL
            agent_card: Optional agent card (will be fetched if not provided)
        """
        if agent_card:
            self._registry.cache_remote_agent(
                agent_id=agent_id,
                agent_card=agent_card,
                endpoint_url=endpoint_url,
            )

        # Create/update HTTP client for this agent
        if endpoint_url not in self._http_clients:
            self._http_clients[endpoint_url] = HttpA2AClient(
                base_url=endpoint_url,
                timeout=self._default_timeout,
                headers=self._headers,
            )
        self._http_clients[endpoint_url].set_agent_endpoint(agent_id, endpoint_url)

    # Client access

    def _get_local_client(self) -> LocalA2AClient:
        """Get or create the local A2A client."""
        if self._local_client is None:
            self._local_client = LocalA2AClient(self._registry)
        return self._local_client

    def _get_gateway_client(self) -> GatewayA2AClient:
        """Get or create the gateway A2A client."""
        if self._gateway_client is None:
            if not self._gateway_url:
                raise ValueError("Gateway URL not configured")
            self._gateway_client = GatewayA2AClient(
                gateway_url=self._gateway_url,
                mode=self._gateway_mode,
                timeout=self._default_timeout,
                headers=self._headers,
            )
        return self._gateway_client

    def _get_client_for_agent(self, agent_id: str) -> A2AClientInterface:
        """Get the appropriate client for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            A2AClientInterface for the agent

        Raises:
            ValueError: If no client can be found for the agent
        """
        # 1. Check if local
        if self._registry.is_local(agent_id):
            logger.debug(f"Routing {agent_id} to LocalA2AClient")
            return self._get_local_client()

        # 2. Check if we have a direct endpoint
        endpoint = self._registry.get_endpoint_url(agent_id)
        if endpoint:
            logger.debug(f"Routing {agent_id} to HttpA2AClient at {endpoint}")
            if endpoint not in self._http_clients:
                self._http_clients[endpoint] = HttpA2AClient(
                    base_url=endpoint,
                    timeout=self._default_timeout,
                    headers=self._headers,
                )
            return self._http_clients[endpoint]

        # 3. Fall back to gateway
        if self._gateway_url:
            logger.debug(f"Routing {agent_id} to GatewayA2AClient")
            return self._get_gateway_client()

        raise ValueError(
            f"No client available for agent '{agent_id}'. "
            "Agent is not local, has no known endpoint, and no gateway is configured."
        )

    # A2AClientInterface implementation

    async def send_task(
        self,
        agent_id: str,
        message: Message,
        *,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        aip_context: Optional[AIPContext] = None,
        stream: bool = False,
    ) -> Union[Task, AsyncGenerator[StreamResponse, None]]:
        """Send a task to an agent, automatically routing to the right client.

        Args:
            agent_id: Target agent identifier
            message: A2A message to send
            task_id: Optional task ID
            context_id: Optional context ID
            aip_context: Optional AIP context
            stream: Whether to stream responses

        Returns:
            Task if stream=False, AsyncGenerator if stream=True

        Raises:
            ValueError: If no client is available for the agent
        """
        client = self._get_client_for_agent(agent_id)
        return await client.send_task(
            agent_id=agent_id,
            message=message,
            task_id=task_id,
            context_id=context_id,
            aip_context=aip_context,
            stream=stream,
        )

    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get agent card, checking local registry first.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCard if found, None otherwise
        """
        # Check local registry
        card = self._registry.get_agent_card(agent_id)
        if card:
            return card

        # Try to fetch from remote
        try:
            client = self._get_client_for_agent(agent_id)
            card = await client.get_agent_card(agent_id)
            if card:
                # Cache for future use
                endpoint = self._registry.get_endpoint_url(agent_id)
                if endpoint:
                    self._registry.cache_remote_agent(agent_id, card, endpoint)
            return card
        except ValueError:
            return None

    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """Cancel a task on an agent.

        Args:
            agent_id: Agent identifier
            task_id: Task to cancel

        Returns:
            True if cancellation was accepted
        """
        try:
            client = self._get_client_for_agent(agent_id)
            return await client.cancel_task(agent_id, task_id)
        except ValueError:
            return False

    async def get_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """Get current task state.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier

        Returns:
            Task if found, None otherwise
        """
        try:
            client = self._get_client_for_agent(agent_id)
            return await client.get_task(agent_id, task_id)
        except ValueError:
            return None

    async def close(self) -> None:
        """Clean up all client resources."""
        if self._local_client:
            await self._local_client.close()
            self._local_client = None

        if self._gateway_client:
            await self._gateway_client.close()
            self._gateway_client = None

        for client in self._http_clients.values():
            await client.close()
        self._http_clients.clear()

    # Convenience methods

    def get_local_agent_ids(self) -> list[str]:
        """Get IDs of all local agents.

        Returns:
            List of local agent IDs
        """
        return self._registry.get_local_agent_ids()

    def list_local_agents(self):
        """List all local agents.

        Returns:
            List of LocalAgentInfo objects
        """
        return self._registry.list_local_agents()

    async def discover_agent(self, endpoint_url: str) -> Optional[AgentCard]:
        """Discover an agent at a given endpoint.

        Args:
            endpoint_url: URL to discover agent at

        Returns:
            AgentCard if found, None otherwise
        """
        client = HttpA2AClient(
            base_url=endpoint_url,
            timeout=self._default_timeout,
            headers=self._headers,
        )
        try:
            # Use a placeholder agent_id for discovery
            card = await client.get_agent_card("discovery")
            if card:
                # Register the discovered agent
                self.register_remote_agent(
                    agent_id=card.name,
                    endpoint_url=endpoint_url,
                    agent_card=card,
                )
            return card
        except Exception as e:
            logger.warning(f"Failed to discover agent at {endpoint_url}: {e}")
            return None
        finally:
            await client.close()

"""HTTP A2A Client - Remote Agent Communication.

This client implements the A2A protocol for remote agents via HTTP,
wrapping the SDK's A2AClient with AIP-specific functionality.

Features:
- Standard A2A protocol over HTTP/SSE
- AIP context embedding in message metadata
- Agent discovery via /.well-known/agent.json
- Streaming and non-streaming task execution
"""

from typing import AsyncGenerator, Dict, Optional, Union
import logging

from unibase_agent_sdk.a2a.types import (
    Task,
    Message,
    AgentCard,
    StreamResponse,
)
from unibase_agent_sdk.a2a.client import (
    A2AClient,
    A2AClientError,
    TaskExecutionError,
)

from aip_sdk.a2a.interface import A2AClientInterface
from aip_sdk.a2a.envelope import AIPContext, wrap_message

logger = logging.getLogger(__name__)


class HttpA2AClient(A2AClientInterface):
    """A2A client for remote agents via HTTP.

    This client communicates with remote A2A-compliant agents over HTTP,
    using JSON-RPC 2.0 for requests and SSE for streaming responses.

    Features:
    - Implements A2AClientInterface for unified client usage
    - Embeds AIP context in A2A message metadata
    - Caches discovered agent cards
    - Supports streaming via SSE

    Example:
        client = HttpA2AClient("https://agent.example.com")

        message = Message.user("What is the weather?")
        task = await client.send_task("weather-agent", message)
        print(task.status.state)
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize HTTP A2A client.

        Args:
            base_url: Base URL for the agent (or gateway)
            timeout: Request timeout in seconds
            headers: Additional headers to include in requests
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = headers or {}
        self._client: Optional[A2AClient] = None
        # Map agent_id to endpoint URL for multi-agent gateways
        self._agent_endpoints: Dict[str, str] = {}

    @property
    def base_url(self) -> str:
        """Get the base URL."""
        return self._base_url

    async def _get_client(self) -> A2AClient:
        """Get or create the underlying HTTP client."""
        if self._client is None:
            self._client = A2AClient(
                timeout=self._timeout,
                headers=self._headers,
            )
            await self._client.__aenter__()
        return self._client

    def _get_agent_url(self, agent_id: str) -> str:
        """Get the endpoint URL for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Full URL for the agent's A2A endpoint
        """
        # Check if we have a specific endpoint for this agent
        if agent_id in self._agent_endpoints:
            return self._agent_endpoints[agent_id]
        # Default to base URL (single-agent mode)
        return self._base_url

    def set_agent_endpoint(self, agent_id: str, endpoint_url: str) -> None:
        """Set the endpoint URL for a specific agent.

        Args:
            agent_id: Agent identifier
            endpoint_url: Full URL for the agent's A2A endpoint
        """
        self._agent_endpoints[agent_id] = endpoint_url.rstrip("/")

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
        """Send a task to a remote agent via HTTP.

        Args:
            agent_id: Target agent identifier
            message: A2A message to send
            task_id: Optional task ID (auto-generated if not provided)
            context_id: Optional context ID for grouping
            aip_context: Optional AIP context for payment/event tracking
            stream: Whether to return streaming response

        Returns:
            Task if stream=False, AsyncGenerator if stream=True

        Raises:
            TaskExecutionError: If task execution fails
        """
        client = await self._get_client()
        agent_url = self._get_agent_url(agent_id)

        # Wrap message with AIP context if provided
        if aip_context:
            message = wrap_message(message, aip_context)

        # Extract metadata from message for the request
        metadata = message.metadata

        logger.debug(f"HttpA2A: Sending task to {agent_id} at {agent_url}")

        if stream:
            return self._stream_task(client, agent_url, message, task_id, context_id)
        else:
            return await client.send_task(
                agent_url=agent_url,
                message=message,
                task_id=task_id,
                context_id=context_id,
                metadata=metadata,
            )

    async def _stream_task(
        self,
        client: A2AClient,
        agent_url: str,
        message: Message,
        task_id: Optional[str],
        context_id: Optional[str],
    ) -> AsyncGenerator[StreamResponse, None]:
        """Stream responses from a remote agent.

        Args:
            client: The A2A client
            agent_url: Agent endpoint URL
            message: Message to send
            task_id: Optional task ID
            context_id: Optional context ID

        Yields:
            StreamResponse events from the agent
        """
        async for response in client.stream_task(
            agent_url=agent_url,
            message=message,
            task_id=task_id,
            context_id=context_id,
        ):
            yield response

    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get agent card for a remote agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCard if agent exists, None otherwise
        """
        client = await self._get_client()
        agent_url = self._get_agent_url(agent_id)

        try:
            return await client.discover_agent(agent_url)
        except A2AClientError as e:
            logger.warning(f"Failed to discover agent {agent_id}: {e}")
            return None

    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """Request task cancellation on a remote agent.

        Args:
            agent_id: Agent identifier
            task_id: Task to cancel

        Returns:
            True if cancellation was accepted
        """
        client = await self._get_client()
        agent_url = self._get_agent_url(agent_id)

        try:
            await client.cancel_task(agent_url, task_id)
            return True
        except TaskExecutionError as e:
            logger.warning(f"Failed to cancel task {task_id}: {e}")
            return False

    async def get_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """Get current task state from a remote agent.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier

        Returns:
            Task if found, None otherwise
        """
        client = await self._get_client()
        agent_url = self._get_agent_url(agent_id)

        try:
            return await client.get_task(agent_url, task_id)
        except TaskExecutionError as e:
            logger.warning(f"Failed to get task {task_id}: {e}")
            return None

    async def close(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.close()
            self._client = None
        self._agent_endpoints.clear()

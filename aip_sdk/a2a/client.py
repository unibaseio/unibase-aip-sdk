"""A2A Protocol Client."""

from typing import Optional, Dict, Any, AsyncIterator, List
import json
import uuid

import httpx

# Import directly from Google A2A SDK
from a2a.types import (
    AgentCard,
    Task,
    Message,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
)
from a2a.client.errors import (
    A2AClientError,
    A2AClientHTTPError,
    A2AClientJSONError,
    A2AClientTimeoutError,
)

# Import Unibase extensions
from .types import StreamResponse


class AgentDiscoveryError(A2AClientError):
    """Error discovering an agent via Agent Card."""
    pass


class TaskExecutionError(A2AClientError):
    """Error executing a task."""

    def __init__(self, message: str, error: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error = error


class A2AClient:
    """Client for communicating with A2A-compliant agents."""

    def __init__(
        self,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize A2A client."""
        self.timeout = timeout
        self._headers = headers or {}
        self._http_client: Optional[httpx.AsyncClient] = None

        # Cache for discovered agents
        self._agent_cache: Dict[str, AgentCard] = {}

    async def __aenter__(self) -> "A2AClient":
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Get HTTP client, creating if needed."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def close(self):
        """Close the client and release resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def health_check(self, agent_url: str) -> bool:
        """Check if a remote agent is healthy and responsive.
        """
        agent_url = agent_url.rstrip("/")

        # Try standard health endpoints
        health_endpoints = ["/health", "/healthz"]

        for endpoint in health_endpoints:
            try:
                response = await self.http_client.get(
                    f"{agent_url}{endpoint}",
                    headers=self._headers,
                    timeout=5.0
                )
                if response.status_code == 200:
                    return True
            except Exception:
                continue

        # Fallback: try to discover agent card as minimal health check
        try:
            await self.discover_agent(agent_url, force_refresh=True)
            return True
        except Exception:
            return False

    async def discover_agent(
        self,
        base_url: str,
        force_refresh: bool = False
    ) -> AgentCard:
        """Discover an agent via its Agent Card."""
        base_url = base_url.rstrip("/")

        # Check cache
        if not force_refresh and base_url in self._agent_cache:
            return self._agent_cache[base_url]

        try:
            response = await self.http_client.get(
                f"{base_url}/.well-known/agent-card.json",
                headers=self._headers
            )
            response.raise_for_status()

            # Use Pydantic model_validate for Google A2A compatibility
            card = AgentCard.model_validate(response.json())
            self._agent_cache[base_url] = card
            return card

        except httpx.HTTPError as e:
            raise AgentDiscoveryError(
                f"Failed to discover agent at {base_url}: {e}"
            )
        except (json.JSONDecodeError, Exception) as e:
            raise AgentDiscoveryError(
                f"Invalid agent card at {base_url}: {e}"
            )

    async def send_task(
        self,
        agent_url: str,
        message: Message,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """Send a task to a remote agent."""
        agent_url = agent_url.rstrip("/")
        if not agent_url.endswith("/a2a"):
            agent_url = f"{agent_url}/a2a"

        # Build request using Google A2A types
        params: Dict[str, Any] = {
            "message": message.model_dump(by_alias=True, exclude_none=True)
        }
        if task_id:
            params["id"] = task_id
        if context_id:
            params["contextId"] = context_id
        if metadata:
            params["metadata"] = metadata

        request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": params,
            "id": str(uuid.uuid4())
        }

        try:
            response = await self.http_client.post(
                agent_url,
                json=request,
                headers={**self._headers, "Content-Type": "application/json"}
            )
            response.raise_for_status()

            data = response.json()
            if "error" in data and data["error"]:
                raise TaskExecutionError(
                    f"Task execution failed: {data['error'].get('message', 'Unknown error')}",
                    error=data["error"]
                )

            # Use Pydantic model_validate for Google A2A compatibility
            return Task.model_validate(data["result"])

        except httpx.HTTPError as e:
            raise TaskExecutionError(f"HTTP error: {e}")
        except (json.JSONDecodeError, KeyError) as e:
            raise TaskExecutionError(f"Invalid response: {e}")

    async def stream_task(
        self,
        agent_url: str,
        message: Message,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> AsyncIterator[StreamResponse]:
        """Stream task responses from a remote agent."""
        agent_url = agent_url.rstrip("/")
        if not agent_url.endswith("/a2a/stream"):
            if agent_url.endswith("/a2a"):
                agent_url = f"{agent_url}/stream"
            else:
                agent_url = f"{agent_url}/a2a/stream"

        params: Dict[str, Any] = {
            "message": message.model_dump(by_alias=True, exclude_none=True)
        }
        if task_id:
            params["id"] = task_id
        if context_id:
            params["contextId"] = context_id

        request = {
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": params,
            "id": str(uuid.uuid4())
        }

        try:
            async with self.http_client.stream(
                "POST",
                agent_url,
                json=request,
                headers={**self._headers, "Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])

                        if "error" in data and data["error"]:
                            raise TaskExecutionError(
                                f"Stream error: {data['error'].get('message', 'Unknown error')}",
                                error=data["error"]
                            )

                        result = data.get("result", {})
                        yield self._parse_stream_response(result)

        except httpx.HTTPError as e:
            raise TaskExecutionError(f"Streaming error: {e}")

    def _parse_stream_response(self, data: Dict[str, Any]) -> StreamResponse:
        """Parse a stream response from raw data."""
        response = StreamResponse()

        if "task" in data:
            response.task = Task.model_validate(data["task"])
        elif "message" in data:
            response.message = Message.model_validate(data["message"])
        elif "statusUpdate" in data:
            update = data["statusUpdate"]
            response.status_update = TaskStatusUpdateEvent.model_validate(update)
        elif "artifactUpdate" in data:
            update = data["artifactUpdate"]
            response.artifact_update = TaskArtifactUpdateEvent.model_validate(update)

        return response

    async def get_task(
        self,
        agent_url: str,
        task_id: str
    ) -> Task:
        """Get a task by ID from a remote agent."""
        agent_url = agent_url.rstrip("/")
        if not agent_url.endswith("/a2a"):
            agent_url = f"{agent_url}/a2a"

        request = {
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "params": {"id": task_id},
            "id": str(uuid.uuid4())
        }

        try:
            response = await self.http_client.post(
                agent_url,
                json=request,
                headers={**self._headers, "Content-Type": "application/json"}
            )
            response.raise_for_status()

            data = response.json()
            if "error" in data and data["error"]:
                raise TaskExecutionError(
                    f"Get task failed: {data['error'].get('message', 'Unknown error')}"
                )

            return Task.model_validate(data["result"])

        except httpx.HTTPError as e:
            raise TaskExecutionError(f"HTTP error: {e}")

    async def list_tasks(
        self,
        agent_url: str,
        context_id: Optional[str] = None
    ) -> List[Task]:
        """List tasks from a remote agent."""
        agent_url = agent_url.rstrip("/")
        if not agent_url.endswith("/a2a"):
            agent_url = f"{agent_url}/a2a"

        params: Dict[str, Any] = {}
        if context_id:
            params["contextId"] = context_id

        request = {
            "jsonrpc": "2.0",
            "method": "tasks/list",
            "params": params,
            "id": str(uuid.uuid4())
        }

        try:
            response = await self.http_client.post(
                agent_url,
                json=request,
                headers={**self._headers, "Content-Type": "application/json"}
            )
            response.raise_for_status()

            data = response.json()
            if "error" in data and data["error"]:
                raise TaskExecutionError(
                    f"List tasks failed: {data['error'].get('message', 'Unknown error')}"
                )

            return [Task.model_validate(t) for t in data["result"].get("tasks", [])]

        except httpx.HTTPError as e:
            raise TaskExecutionError(f"HTTP error: {e}")

    async def cancel_task(
        self,
        agent_url: str,
        task_id: str
    ) -> Task:
        """Cancel a task on a remote agent."""
        agent_url = agent_url.rstrip("/")
        if not agent_url.endswith("/a2a"):
            agent_url = f"{agent_url}/a2a"

        request = {
            "jsonrpc": "2.0",
            "method": "tasks/cancel",
            "params": {"id": task_id},
            "id": str(uuid.uuid4())
        }

        try:
            response = await self.http_client.post(
                agent_url,
                json=request,
                headers={**self._headers, "Content-Type": "application/json"}
            )
            response.raise_for_status()

            data = response.json()
            if "error" in data and data["error"]:
                raise TaskExecutionError(
                    f"Cancel task failed: {data['error'].get('message', 'Unknown error')}"
                )

            return Task.model_validate(data["result"])

        except httpx.HTTPError as e:
            raise TaskExecutionError(f"HTTP error: {e}")

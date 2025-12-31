"""Gateway A2A Client - Gateway-mediated Agent Communication.

This client implements A2A protocol for agents accessed through a gateway,
supporting both Push mode (gateway forwards requests) and Pull mode
(agents poll for tasks).

Gateway Modes:
- Push Mode: Gateway forwards A2A requests to agent endpoint
- Pull Mode: Tasks are queued, agents poll and respond

In both modes, this client provides a unified A2A interface to callers,
abstracting the underlying gateway mechanics.
"""

from typing import AsyncGenerator, Dict, Optional, Union
import asyncio
import logging
import uuid
import httpx

from unibase_agent_sdk.a2a.types import (
    Task,
    TaskState,
    TaskStatus,
    Message,
    AgentCard,
    StreamResponse,
    TaskStatusUpdateEvent,
    JSONRPCRequest,
)

from aip_sdk.a2a.interface import A2AClientInterface
from aip_sdk.a2a.envelope import AIPContext, wrap_message

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """Gateway communication error."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class TaskTimeoutError(Exception):
    """Task execution timed out."""

    def __init__(self, task_id: str, timeout: float):
        self.task_id = task_id
        self.timeout = timeout
        super().__init__(f"Task {task_id} timed out after {timeout}s")


class GatewayA2AClient(A2AClientInterface):
    """A2A client for gateway-mediated agent communication.

    This client routes A2A requests through a gateway, which then either:
    - Push Mode: Forwards the request to the agent's HTTP endpoint
    - Pull Mode: Queues the task for the agent to poll

    The client abstracts these modes, providing a consistent A2A interface.

    Features:
    - Transparent Push/Pull mode handling
    - Task status polling for Pull mode
    - AIP context propagation
    - Streaming support (in Push mode)

    Example:
        client = GatewayA2AClient(
            gateway_url="https://gateway.example.com",
            mode="push"  # or "pull"
        )

        message = Message.user("Hello")
        task = await client.send_task("remote-agent", message)
    """

    def __init__(
        self,
        gateway_url: str,
        *,
        mode: str = "push",
        timeout: float = 30.0,
        poll_interval: float = 1.0,
        max_poll_time: float = 300.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize Gateway A2A client.

        Args:
            gateway_url: Gateway base URL
            mode: Gateway mode - "push" or "pull"
            timeout: Request timeout in seconds
            poll_interval: Interval for polling task status (Pull mode)
            max_poll_time: Maximum time to poll for task completion
            headers: Additional headers for requests
        """
        self._gateway_url = gateway_url.rstrip("/")
        self._mode = mode
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._max_poll_time = max_poll_time
        self._headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

        # Cache for agent cards
        self._agent_cards: Dict[str, AgentCard] = {}
        # Pending tasks for tracking
        self._pending_tasks: Dict[str, Task] = {}

    @property
    def gateway_url(self) -> str:
        """Get the gateway URL."""
        return self._gateway_url

    @property
    def mode(self) -> str:
        """Get the gateway mode."""
        return self._mode

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

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
        """Send a task through the gateway.

        Args:
            agent_id: Target agent identifier
            message: A2A message to send
            task_id: Optional task ID (auto-generated if not provided)
            context_id: Optional context ID for grouping
            aip_context: Optional AIP context
            stream: Whether to return streaming response

        Returns:
            Task if stream=False, AsyncGenerator if stream=True

        Raises:
            GatewayError: If gateway communication fails
            TaskTimeoutError: If task times out (Pull mode)
        """
        # Wrap message with AIP context if provided
        if aip_context:
            message = wrap_message(message, aip_context)

        # Generate task ID if not provided
        task_id = task_id or str(uuid.uuid4())

        logger.debug(f"GatewayA2A: Sending task {task_id} to {agent_id} via {self._mode} mode")

        if self._mode == "push":
            if stream:
                return self._push_stream(agent_id, message, task_id, context_id)
            else:
                return await self._push_send(agent_id, message, task_id, context_id)
        else:  # pull mode
            # Pull mode doesn't support true streaming from client perspective
            return await self._pull_send(agent_id, message, task_id, context_id)

    async def _push_send(
        self,
        agent_id: str,
        message: Message,
        task_id: str,
        context_id: Optional[str],
    ) -> Task:
        """Send task via Push mode (gateway forwards to agent).

        Args:
            agent_id: Target agent
            message: Message to send
            task_id: Task ID
            context_id: Optional context ID

        Returns:
            Completed Task from agent
        """
        client = await self._get_client()

        # Build JSON-RPC request
        params = {
            "id": task_id,
            "message": message.to_dict(),
        }
        if context_id:
            params["contextId"] = context_id
        if message.metadata:
            params["metadata"] = message.metadata

        request = JSONRPCRequest(
            method="message/send",
            params=params,
            id=str(uuid.uuid4()),
        )

        try:
            # Gateway A2A endpoint: /gateway/a2a/{agent_id}
            response = await client.post(
                f"{self._gateway_url}/gateway/a2a/{agent_id}",
                json=request.to_dict(),
                headers={**self._headers, "Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            if "error" in data and data["error"]:
                raise GatewayError(
                    f"Task failed: {data['error']['message']}",
                    status_code=data["error"].get("code"),
                )

            return Task.from_dict(data["result"])

        except httpx.HTTPStatusError as e:
            raise GatewayError(
                f"Gateway error: {e.response.status_code}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            raise GatewayError(f"Request error: {e}")

    async def _push_stream(
        self,
        agent_id: str,
        message: Message,
        task_id: str,
        context_id: Optional[str],
    ) -> AsyncGenerator[StreamResponse, None]:
        """Stream task via Push mode.

        Args:
            agent_id: Target agent
            message: Message to send
            task_id: Task ID
            context_id: Optional context ID

        Yields:
            StreamResponse events from agent
        """
        client = await self._get_client()

        params = {
            "id": task_id,
            "message": message.to_dict(),
        }
        if context_id:
            params["contextId"] = context_id

        request = JSONRPCRequest(
            method="message/stream",
            params=params,
            id=str(uuid.uuid4()),
        )

        try:
            async with client.stream(
                "POST",
                f"{self._gateway_url}/gateway/a2a/{agent_id}/stream",
                json=request.to_dict(),
                headers={**self._headers, "Content-Type": "application/json"},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        data = json.loads(line[6:])

                        if "error" in data and data["error"]:
                            raise GatewayError(
                                f"Stream error: {data['error']['message']}"
                            )

                        result = data.get("result", {})
                        yield self._parse_stream_response(result)

        except httpx.HTTPStatusError as e:
            raise GatewayError(
                f"Gateway stream error: {e.response.status_code}",
                status_code=e.response.status_code,
            )

    async def _pull_send(
        self,
        agent_id: str,
        message: Message,
        task_id: str,
        context_id: Optional[str],
    ) -> Task:
        """Send task via Pull mode (task queued for agent to poll).

        This method:
        1. Submits the task to the gateway queue
        2. Polls for task completion
        3. Returns completed task

        Args:
            agent_id: Target agent
            message: Message to send
            task_id: Task ID
            context_id: Optional context ID

        Returns:
            Completed Task
        """
        client = await self._get_client()

        # Create initial task
        task = Task(
            id=task_id,
            context_id=context_id,
            status=TaskStatus(state=TaskState.SUBMITTED),
            history=[message],
        )
        self._pending_tasks[task_id] = task

        # Submit to gateway task queue
        try:
            response = await client.post(
                f"{self._gateway_url}/gateway/tasks/submit",
                json={
                    "task_id": task_id,
                    "agent": agent_id,
                    "payload": {
                        "message": message.to_dict(),
                        "context_id": context_id,
                        "metadata": message.metadata,
                    },
                },
                headers=self._headers,
            )
            response.raise_for_status()

            logger.debug(f"Task {task_id} submitted to gateway queue")

        except httpx.HTTPStatusError as e:
            task.status = TaskStatus(
                state=TaskState.FAILED,
                message=Message.agent(f"Gateway error: {e.response.status_code}"),
            )
            return task
        except httpx.RequestError as e:
            task.status = TaskStatus(
                state=TaskState.FAILED,
                message=Message.agent(f"Request error: {e}"),
            )
            return task

        # Poll for completion
        task.status = TaskStatus(state=TaskState.WORKING)
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self._max_poll_time:
                task.status = TaskStatus(
                    state=TaskState.FAILED,
                    message=Message.agent(f"Task timed out after {self._max_poll_time}s"),
                )
                raise TaskTimeoutError(task_id, self._max_poll_time)

            await asyncio.sleep(self._poll_interval)

            try:
                response = await client.get(
                    f"{self._gateway_url}/gateway/tasks/{task_id}/status",
                    headers=self._headers,
                )
                response.raise_for_status()
                data = response.json()

                status = data.get("status", "pending")
                logger.debug(f"Task {task_id} status: {status}")

                if status == "completed":
                    # Fetch full result
                    result_response = await client.get(
                        f"{self._gateway_url}/gateway/tasks/{task_id}/result",
                        headers=self._headers,
                    )
                    result_response.raise_for_status()
                    result_data = result_response.json()

                    # Update task with result
                    task.status = TaskStatus(state=TaskState.COMPLETED)
                    if "result" in result_data:
                        # Parse result into task format
                        self._apply_result(task, result_data["result"])

                    del self._pending_tasks[task_id]
                    return task

                elif status == "failed":
                    error_msg = data.get("error", "Unknown error")
                    task.status = TaskStatus(
                        state=TaskState.FAILED,
                        message=Message.agent(error_msg),
                    )
                    del self._pending_tasks[task_id]
                    return task

                elif status == "canceled":
                    task.status = TaskStatus(state=TaskState.CANCELED)
                    del self._pending_tasks[task_id]
                    return task

            except httpx.RequestError as e:
                logger.warning(f"Error polling task status: {e}")
                # Continue polling

    def _apply_result(self, task: Task, result: Dict) -> None:
        """Apply result data to task.

        Args:
            task: Task to update
            result: Result dictionary from gateway
        """
        from unibase_agent_sdk.a2a.types import TextPart, Artifact

        # Handle different result formats
        if "message" in result:
            # A2A message format
            task.history.append(Message.from_dict(result["message"]))

        elif "text" in result or "response" in result:
            # Simple text response
            text = result.get("text") or result.get("response", "")
            task.history.append(Message.agent(text))

        elif "result" in result:
            # Nested result (common gateway format)
            nested = result["result"]
            if isinstance(nested, str):
                task.history.append(Message.agent(nested))
            elif isinstance(nested, dict):
                import json
                task.history.append(Message.agent(json.dumps(nested)))

        # Handle artifacts if present
        if "artifacts" in result:
            for artifact_data in result["artifacts"]:
                task.artifacts.append(Artifact.from_dict(artifact_data))

    def _parse_stream_response(self, data: Dict) -> StreamResponse:
        """Parse stream response data.

        Args:
            data: Response data dictionary

        Returns:
            StreamResponse object
        """
        from unibase_agent_sdk.a2a.types import (
            TaskStatusUpdateEvent,
            TaskArtifactUpdateEvent,
            TaskStatus,
            Artifact,
        )

        response = StreamResponse()

        if "task" in data:
            response.task = Task.from_dict(data["task"])
        elif "message" in data:
            response.message = Message.from_dict(data["message"])
        elif "statusUpdate" in data:
            update = data["statusUpdate"]
            response.status_update = TaskStatusUpdateEvent(
                task_id=update["taskId"],
                context_id=update.get("contextId"),
                status=TaskStatus.from_dict(update["status"]),
                final=update.get("final", False),
            )
        elif "artifactUpdate" in data:
            update = data["artifactUpdate"]
            response.artifact_update = TaskArtifactUpdateEvent(
                task_id=update["taskId"],
                context_id=update.get("contextId"),
                artifact=Artifact.from_dict(update["artifact"]),
            )

        return response

    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get agent card via gateway.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCard if found, None otherwise
        """
        if agent_id in self._agent_cards:
            return self._agent_cards[agent_id]

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._gateway_url}/gateway/agents/{agent_id}/card",
                headers=self._headers,
            )
            response.raise_for_status()

            card = AgentCard.from_dict(response.json())
            self._agent_cards[agent_id] = card
            return card

        except httpx.HTTPStatusError:
            return None
        except Exception as e:
            logger.warning(f"Error fetching agent card for {agent_id}: {e}")
            return None

    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """Cancel a task via gateway.

        Args:
            agent_id: Agent identifier
            task_id: Task to cancel

        Returns:
            True if cancellation was accepted
        """
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self._gateway_url}/gateway/tasks/{task_id}/cancel",
                json={"agent": agent_id},
                headers=self._headers,
            )
            response.raise_for_status()

            # Update local tracking
            if task_id in self._pending_tasks:
                self._pending_tasks[task_id].status = TaskStatus(
                    state=TaskState.CANCELED
                )

            return True

        except httpx.HTTPStatusError:
            return False
        except Exception as e:
            logger.warning(f"Error canceling task {task_id}: {e}")
            return False

    async def get_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """Get task status via gateway.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier

        Returns:
            Task if found, None otherwise
        """
        # Check local cache first
        if task_id in self._pending_tasks:
            return self._pending_tasks[task_id]

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._gateway_url}/gateway/tasks/{task_id}",
                headers=self._headers,
            )
            response.raise_for_status()

            data = response.json()
            return Task.from_dict(data)

        except httpx.HTTPStatusError:
            return None
        except Exception as e:
            logger.warning(f"Error getting task {task_id}: {e}")
            return None

    async def close(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._pending_tasks.clear()
        self._agent_cards.clear()

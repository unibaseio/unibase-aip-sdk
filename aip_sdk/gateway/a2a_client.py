"""Gateway A2A Client - Gateway-mediated Agent Communication."""

from typing import TYPE_CHECKING, AsyncGenerator, Dict, Optional, Union
import asyncio
import logging
import uuid
import httpx

from a2a.types import (
    Task,
    TaskState,
    TaskStatus,
    Message,
    Role,
    AgentCard,
    TaskStatusUpdateEvent,
    JSONRPCRequest,
)

from aip_sdk.gateway.interface import A2AClientInterface
from aip_sdk.agent.context import AIPContext, wrap_message

if TYPE_CHECKING:
    from unibase_agent_sdk.a2a import StreamResponse

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
    """A2A client for gateway-mediated agent communication."""

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
        """Initialize Gateway A2A client."""
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
    ) -> Union[Task, AsyncGenerator["StreamResponse", None]]:
        """Send a task through the gateway."""
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
        """Send task via Push mode (gateway forwards to agent)."""
        client = await self._get_client()

        # Build JSON-RPC request
        params = {
            "id": task_id,
            "message": message.model_dump(mode='json'),
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
                json=request.model_dump(mode='json'),
                headers={**self._headers, "Content-Type": "application/json"},
            )
            response.raise_for_status()

            data = response.json()
            if "error" in data and data["error"]:
                raise GatewayError(
                    f"Task failed: {data['error']['message']}",
                    status_code=data["error"].get("code"),
                )

            result = data.get("result", {})

            # Expect A2A Task object
            return Task.model_validate(result)

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
    ) -> AsyncGenerator["StreamResponse", None]:
        """Stream task via Push mode."""
        client = await self._get_client()

        params = {
            "id": task_id,
            "message": message.model_dump(mode='json'),
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
                json=request.model_dump(mode='json'),
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
        """Send task via Pull mode (task queued for agent to poll)."""
        client = await self._get_client()

        # Create initial task
        task = Task(
            id=task_id,
            context_id=context_id or task_id,
            status=TaskStatus(state=TaskState.submitted),
            history=[message],
        )
        self._pending_tasks[task_id] = task

        # Extract handle from agent_id (format: erc8004:handle or just handle)
        agent_handle = agent_id.split(":")[-1] if ":" in agent_id else agent_id

        # Submit to gateway task queue
        # Construct A2A JSON-RPC message/send request
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "params": {
                "message": message.model_dump(mode='json'),
                "id": task_id,
                "contextId": context_id,
            },
            "id": task_id,
        }

        try:
            response = await client.post(
                f"{self._gateway_url}/gateway/tasks/submit",
                json={
                    "task_id": task_id,
                    "agent": agent_handle,  # Use handle, not full agent_id
                    "payload": jsonrpc_request,  # Send complete JSON-RPC request
                },
                headers=self._headers,
            )
            response.raise_for_status()

            logger.debug(f"Task {task_id} submitted to gateway queue for agent {agent_handle}")

        except httpx.HTTPStatusError as e:
            task.status = TaskStatus(
                state=TaskState.failed,
                message=Message.agent(f"Gateway error: {e.response.status_code}"),
            )
            return task
        except httpx.RequestError as e:
            task.status = TaskStatus(
                state=TaskState.failed,
                message=Message.agent(f"Request error: {e}"),
            )
            return task

        # Poll for completion
        task.status = TaskStatus(state=TaskState.working)
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self._max_poll_time:
                task.status = TaskStatus(
                    state=TaskState.failed,
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
                print(f"[DEBUG _pull_send] Task {task_id} status: {status}")
                logger.debug(f"[_pull_send] Task {task_id} status: {status}")

                if status == "completed":
                    print(f"[DEBUG _pull_send] Task completed, fetching result...")
                    logger.debug(f"[_pull_send] Task completed, fetching result...")
                    # Fetch full result
                    result_response = await client.get(
                        f"{self._gateway_url}/gateway/tasks/{task_id}/result",
                        headers=self._headers,
                    )
                    result_response.raise_for_status()
                    result_data = result_response.json()
                    print(f"[DEBUG _pull_send] Result data keys: {list(result_data.keys())}")
                    print(f"[DEBUG _pull_send] Has 'result' key: {'result' in result_data}")
                    logger.debug(f"[_pull_send] Result data keys: {result_data.keys()}")
                    logger.debug(f"[_pull_send] Has 'result' key: {'result' in result_data}")

                    # Update task with result
                    task.status = TaskStatus(state=TaskState.completed)
                    if "result" in result_data:
                        print(f"[DEBUG _pull_send] Calling _apply_result...")
                        logger.debug(f"[_pull_send] Calling _apply_result...")
                        # Parse result into task format
                        self._apply_result(task, result_data["result"])
                        print(f"[DEBUG _pull_send] After _apply_result, task.history length: {len(task.history)}")
                        logger.debug(f"[_pull_send] After _apply_result, task.history length: {len(task.history)}")

                    del self._pending_tasks[task_id]
                    return task

                elif status == "failed":
                    error_msg = data.get("error", "Unknown error")
                    task.status = TaskStatus(
                        state=TaskState.failed,
                        message=Message.agent(error_msg),
                    )
                    del self._pending_tasks[task_id]
                    return task

                elif status == "canceled":
                    task.status = TaskStatus(state=TaskState.canceled)
                    del self._pending_tasks[task_id]
                    return task

            except httpx.RequestError as e:
                logger.warning(f"Error polling task status: {e}")
                # Continue polling

    def _apply_result(self, task: Task, result: Dict) -> None:
        """Apply result data to task."""
        from a2a.types import Artifact
        import json

        # Debug logging
        logger.debug(f"[_apply_result] Called with result keys: {result.keys()}")
        logger.debug(f"[_apply_result] Result type: {type(result)}")
        logger.debug(f"[_apply_result] Result preview: {json.dumps(result, indent=2)[:500]}")

        # Result is a JSON-RPC response: {"jsonrpc": "2.0", "id": "...", "result": {...}}
        # The actual task data is in result["result"]
        task_data = result.get("result", result)  # Fall back to result if no nested "result"

        logger.debug(f"[_apply_result] Task data keys: {task_data.keys() if isinstance(task_data, dict) else 'not a dict'}")

        # Task data should be a complete Task object from agent
        # Extract history (messages) and artifacts from it
        if "history" in task_data:
            logger.debug(f"[_apply_result] Found history with {len(task_data['history'])} messages")
            print(f"[DEBUG _apply_result] Found history with {len(task_data['history'])} messages")
            # History is an array of messages - add agent messages to task
            agent_msg_count = 0
            for i, msg_data in enumerate(task_data["history"]):
                msg = Message.model_validate(msg_data)
                logger.debug(f"[_apply_result] Message {i+1}: role={msg.role}")
                print(f"[DEBUG _apply_result] Message {i+1}: role={msg.role}")
                # Only add agent messages (skip user messages that are already in history)
                if msg.role == Role.agent:
                    agent_msg_count += 1
                    from a2a.utils.message import get_message_text
                    msg_text = get_message_text(msg)
                    logger.debug(f"[_apply_result] Adding agent message #{agent_msg_count} to task.history, text preview: {msg_text[:100] if msg_text else 'None'}")
                    print(f"[DEBUG _apply_result] Adding agent message #{agent_msg_count}, text preview: {msg_text[:100] if msg_text else 'None'}")
                    task.history.append(msg)
            print(f"[DEBUG _apply_result] Total agent messages added: {agent_msg_count}")
            logger.debug(f"[_apply_result] Total agent messages added: {agent_msg_count}")
            print(f"[DEBUG _apply_result] Task.history now has {len(task.history)} total messages")
            logger.debug(f"[_apply_result] Task.history now has {len(task.history)} total messages")
        else:
            logger.warning(f"[_apply_result] No history found in task_data!")
            print(f"[DEBUG _apply_result] WARNING: No history found in task_data!")

        # Handle artifacts if present
        if "artifacts" in task_data and task_data["artifacts"]:
            for artifact_data in task_data["artifacts"]:
                task.artifacts.append(Artifact.model_validate(artifact_data))

    def _parse_stream_response(self, data: Dict) -> "StreamResponse":
        """Parse stream response data."""
        from a2a.types import (
            TaskStatusUpdateEvent,
            TaskArtifactUpdateEvent,
            TaskStatus,
            Artifact,
        )
        from unibase_agent_sdk.a2a import StreamResponse

        response = StreamResponse()

        if "task" in data:
            response.task = Task.model_validate(data["task"])
        elif "message" in data:
            response.message = Message.model_validate(data["message"])
        elif "statusUpdate" in data:
            update = data["statusUpdate"]
            response.status_update = TaskStatusUpdateEvent(
                task_id=update["taskId"],
                context_id=update.get("contextId"),
                status=TaskStatus.model_validate(update["status"]),
                final=update.get("final", False),
            )
        elif "artifactUpdate" in data:
            update = data["artifactUpdate"]
            response.artifact_update = TaskArtifactUpdateEvent(
                task_id=update["taskId"],
                context_id=update.get("contextId"),
                artifact=Artifact.model_validate(update["artifact"]),
            )

        return response

    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get agent card via gateway."""
        if agent_id in self._agent_cards:
            return self._agent_cards[agent_id]

        client = await self._get_client()

        try:
            response = await client.get(
                f"{self._gateway_url}/gateway/agents/{agent_id}/card",
                headers=self._headers,
            )
            response.raise_for_status()

            card = AgentCard.model_validate(response.json())
            self._agent_cards[agent_id] = card
            return card

        except httpx.HTTPStatusError:
            return None
        except Exception as e:
            logger.warning(f"Error fetching agent card for {agent_id}: {e}")
            return None

    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """Cancel a task via gateway."""
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
                    state=TaskState.canceled
                )

            return True

        except httpx.HTTPStatusError:
            return False
        except Exception as e:
            logger.warning(f"Error canceling task {task_id}: {e}")
            return False

    async def get_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """Get task status via gateway."""
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
            return Task.model_validate(data)

        except httpx.HTTPStatusError:
            return None
        except Exception as e:
            logger.warning(f"Error getting task {task_id}: {e}")
            return None

    async def discover_agent(self, endpoint_url: str) -> Optional[AgentCard]:
        """Discover an agent at a given endpoint via gateway.

        Args:
            endpoint_url: The endpoint URL of the agent to discover.

        Returns:
            The AgentCard if discovered, None otherwise.
        """
        client = await self._get_client()
        endpoint_url = endpoint_url.rstrip("/")

        try:
            # Try to fetch agent card from the endpoint
            response = await client.get(
                f"{endpoint_url}/.well-known/agent.json",
                headers=self._headers,
            )
            response.raise_for_status()

            card = AgentCard.model_validate(response.json())
            # Cache the discovered agent
            self._agent_cards[card.name] = card
            logger.info(f"Discovered agent: {card.name} at {endpoint_url}")
            return card

        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to discover agent at {endpoint_url}: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.warning(f"Failed to discover agent at {endpoint_url}: {e}")
            return None

    async def close(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._pending_tasks.clear()
        self._agent_cards.clear()

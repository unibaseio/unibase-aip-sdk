"""Local A2A Client - In-Process Agent Communication.

This client implements the A2A protocol for local (in-process) agents,
providing the same interface as HTTP-based clients but without network overhead.

The key benefit is that local agent-to-agent calls use the standard A2A
message format while avoiding serialization and network latency.
"""

from typing import AsyncGenerator, Optional, Union
import uuid
import logging

from unibase_agent_sdk.a2a.types import (
    Task,
    TaskState,
    TaskStatus,
    Message,
    AgentCard,
    StreamResponse,
    TaskStatusUpdateEvent,
)

from aip_sdk.a2a.interface import A2AClientInterface
from aip_sdk.a2a.envelope import AIPContext, wrap_message
from aip_sdk.a2a.registry import LocalAgentRegistry

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """Raised when an agent cannot be found."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent not found: {agent_id}")


class LocalA2AClient(A2AClientInterface):
    """A2A client for local (in-process) agents.

    This client calls agents directly within the same process,
    using the A2A protocol format but without network overhead.

    Features:
    - Direct function calls to agent TaskHandlers
    - Same A2A message format as remote calls
    - Support for streaming responses
    - Zero serialization overhead for local calls

    Example:
        registry = LocalAgentRegistry()
        client = LocalA2AClient(registry)

        message = Message.user("What is 2+2?")
        task = await client.send_task("calculator", message)
        print(task.status.state)  # TaskState.COMPLETED
    """

    def __init__(self, registry: LocalAgentRegistry):
        """Initialize local A2A client.

        Args:
            registry: LocalAgentRegistry containing agent handlers
        """
        self._registry = registry
        # Task storage for get_task support
        self._tasks: dict[str, Task] = {}

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
        """Send a task to a local agent.

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
            AgentNotFoundError: If agent is not registered locally
        """
        # Look up local agent
        agent_info = self._registry.get_local_agent(agent_id)
        if not agent_info:
            raise AgentNotFoundError(agent_id)

        # Wrap message with AIP context if provided
        if aip_context:
            message = wrap_message(message, aip_context)

        # Create task
        task = Task(
            id=task_id or str(uuid.uuid4()),
            status=TaskStatus(state=TaskState.SUBMITTED),
            context_id=context_id,
            history=[message],
        )

        logger.debug(f"LocalA2A: Sending task {task.id} to agent {agent_id}")

        if stream:
            return self._stream_handler(agent_info.task_handler, task)
        else:
            return await self._run_handler(agent_info.task_handler, task)

    async def _run_handler(
        self,
        handler,
        task: Task,
    ) -> Task:
        """Execute handler and collect all responses into task.

        Args:
            handler: TaskHandler to call
            task: Task to process

        Returns:
            Updated Task with results
        """
        task.status = TaskStatus(state=TaskState.WORKING)
        self._tasks[task.id] = task

        try:
            async for response in handler(task):
                self._apply_response(task, response)

            # If still working after handler completes, mark as completed
            if task.status.state == TaskState.WORKING:
                task.status = TaskStatus(state=TaskState.COMPLETED)

        except Exception as e:
            logger.exception(f"LocalA2A: Handler error for task {task.id}")
            task.status = TaskStatus(
                state=TaskState.FAILED,
                message=Message.agent(str(e)),
            )

        self._tasks[task.id] = task
        logger.debug(f"LocalA2A: Task {task.id} completed with state {task.status.state}")
        return task

    async def _stream_handler(
        self,
        handler,
        task: Task,
    ) -> AsyncGenerator[StreamResponse, None]:
        """Execute handler and yield streaming responses.

        Args:
            handler: TaskHandler to call
            task: Task to process

        Yields:
            StreamResponse events from the handler
        """
        task.status = TaskStatus(state=TaskState.WORKING)
        self._tasks[task.id] = task

        # Yield initial status
        yield StreamResponse(
            status_update=TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=task.status,
            )
        )

        try:
            async for response in handler(task):
                self._apply_response(task, response)
                yield response

            # If still working, emit completion
            if task.status.state == TaskState.WORKING:
                task.status = TaskStatus(state=TaskState.COMPLETED)
                yield StreamResponse(
                    status_update=TaskStatusUpdateEvent(
                        task_id=task.id,
                        context_id=task.context_id,
                        status=task.status,
                        final=True,
                    )
                )

        except Exception as e:
            logger.exception(f"LocalA2A: Handler error for task {task.id}")
            task.status = TaskStatus(
                state=TaskState.FAILED,
                message=Message.agent(str(e)),
            )
            yield StreamResponse(
                status_update=TaskStatusUpdateEvent(
                    task_id=task.id,
                    context_id=task.context_id,
                    status=task.status,
                    final=True,
                )
            )

        self._tasks[task.id] = task

    def _apply_response(self, task: Task, response: StreamResponse) -> None:
        """Apply a StreamResponse to update task state.

        Args:
            task: Task to update
            response: Response to apply
        """
        if response.task:
            # Full task replacement
            task.status = response.task.status
            task.artifacts = response.task.artifacts
            task.history = response.task.history

        elif response.status_update:
            task.status = response.status_update.status

        elif response.artifact_update:
            artifact = response.artifact_update.artifact
            # Find existing artifact by index or append
            existing = next(
                (a for a in task.artifacts if a.index == artifact.index),
                None
            )
            if existing and artifact.append:
                # Append to existing artifact
                existing.parts.extend(artifact.parts)
                existing.last_chunk = artifact.last_chunk
            else:
                # Add new or replace artifact
                task.artifacts = [
                    a for a in task.artifacts if a.index != artifact.index
                ]
                task.artifacts.append(artifact)
                task.artifacts.sort(key=lambda a: a.index)

        elif response.message:
            task.history.append(response.message)

    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get agent card for a local agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCard if agent exists, None otherwise
        """
        agent_info = self._registry.get_local_agent(agent_id)
        if agent_info:
            return agent_info.agent_card
        return None

    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """Request task cancellation.

        Note: Local tasks don't support true cancellation yet.
        This marks the task as canceled but doesn't interrupt execution.

        Args:
            agent_id: Agent identifier
            task_id: Task to cancel

        Returns:
            True if task was found and marked canceled
        """
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus(state=TaskState.CANCELED)
            return True
        return False

    async def get_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """Get current task state.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier

        Returns:
            Task if found, None otherwise
        """
        return self._tasks.get(task_id)

    async def close(self) -> None:
        """Clean up resources."""
        self._tasks.clear()

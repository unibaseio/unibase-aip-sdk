"""A2A Client Interface and Task Handler Types.

Defines the abstract interface for all A2A clients and the TaskHandler type
that agents must implement.
"""

from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Optional,
    Union,
)

from unibase_agent_sdk.a2a.types import (
    Task,
    Message,
    AgentCard,
    StreamResponse,
)

from aip_sdk.a2a.envelope import AIPContext


# Type alias for task handlers
# A TaskHandler receives a Task and yields StreamResponse events
TaskHandler = Callable[[Task], AsyncGenerator[StreamResponse, None]]


class A2AClientInterface(ABC):
    """Abstract interface for A2A clients.

    All A2A clients (local, HTTP, gateway) implement this interface,
    enabling the factory to transparently route to the appropriate transport.
    """

    @abstractmethod
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
        """Send a task to an agent.

        Args:
            agent_id: Target agent identifier
            message: A2A message to send
            task_id: Optional task ID (auto-generated if not provided)
            context_id: Optional context ID for grouping related tasks
            aip_context: Optional AIP context for payment/event tracking
            stream: Whether to return streaming response

        Returns:
            Task if stream=False, AsyncGenerator of StreamResponse if stream=True
        """
        ...

    @abstractmethod
    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get the agent card (capabilities) for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCard if found, None otherwise
        """
        ...

    @abstractmethod
    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """Request cancellation of a task.

        Args:
            agent_id: Agent that owns the task
            task_id: Task to cancel

        Returns:
            True if cancellation was accepted
        """
        ...

    @abstractmethod
    async def get_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """Get current state of a task.

        Args:
            agent_id: Agent that owns the task
            task_id: Task to retrieve

        Returns:
            Task if found, None otherwise
        """
        ...

    async def close(self) -> None:
        """Clean up resources. Override in subclasses if needed."""
        pass

    async def __aenter__(self) -> "A2AClientInterface":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

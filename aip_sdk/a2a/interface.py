"""A2A Client Interface and Task Handler Types."""

from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Optional,
    Union,
)

from a2a.types import Task, Message, AgentCard
from unibase_agent_sdk.a2a import StreamResponse

from aip_sdk.a2a.envelope import AIPContext


# Type alias for task handlers
# A TaskHandler receives a Task and yields StreamResponse events
TaskHandler = Callable[[Task], AsyncGenerator[StreamResponse, None]]


class A2AClientInterface(ABC):
    """Abstract interface for A2A clients."""

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
        """Send a task to an agent."""
        ...

    @abstractmethod
    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get the agent card (capabilities) for an agent."""
        ...

    @abstractmethod
    async def cancel_task(self, agent_id: str, task_id: str) -> bool:
        """Request cancellation of a task."""
        ...

    @abstractmethod
    async def get_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """Get current state of a task."""
        ...

    async def close(self) -> None:
        """Clean up resources. Override in subclasses if needed."""
        pass

    async def __aenter__(self) -> "A2AClientInterface":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

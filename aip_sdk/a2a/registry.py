"""Local Agent Registry.

Manages registration and lookup of local (in-process) agents.
Each agent is registered with its TaskHandler and AgentCard.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING
import logging

from unibase_agent_sdk.a2a.types import AgentCard

from aip_sdk.a2a.interface import TaskHandler

logger = logging.getLogger(__name__)


@dataclass
class LocalAgentInfo:
    """Information about a locally registered agent.

    Attributes:
        agent_id: Unique agent identifier
        task_handler: A2A TaskHandler for processing tasks
        agent_card: A2A AgentCard describing capabilities
        agent_instance: Optional reference to the original Agent object
        endpoint_url: Optional URL if agent also exposed via HTTP
        gateway_mode: Optional gateway mode ("push" or "pull")
    """
    agent_id: str
    task_handler: TaskHandler
    agent_card: AgentCard
    agent_instance: Optional[object] = None
    endpoint_url: Optional[str] = None
    gateway_mode: Optional[str] = None  # "push", "pull", or None for local-only


@dataclass
class RemoteAgentInfo:
    """Information about a discovered remote agent.

    Attributes:
        agent_id: Agent identifier
        agent_card: A2A AgentCard
        endpoint_url: URL to the agent's A2A endpoint
        gateway_mode: Optional gateway mode if behind gateway
    """
    agent_id: str
    agent_card: AgentCard
    endpoint_url: str
    gateway_mode: Optional[str] = None


class LocalAgentRegistry:
    """Registry for local (in-process) agents.

    This registry manages agents running in the same process.
    It provides:
    - Registration of agents with their TaskHandlers
    - Lookup by agent ID
    - Discovery of all local agents
    - Caching of remote agent cards

    Example:
        registry = LocalAgentRegistry()

        # Register a local agent
        registry.register_local(
            agent_id="calculator",
            task_handler=calculator_handler,
            agent_card=calculator_card,
        )

        # Check if agent is local
        if registry.is_local("calculator"):
            info = registry.get_local_agent("calculator")
            handler = info.task_handler
    """

    def __init__(self):
        self._local_agents: Dict[str, LocalAgentInfo] = {}
        self._remote_agents: Dict[str, RemoteAgentInfo] = {}
        self._a2a_client_factory: Optional["A2AClientFactory"] = None

    def register_local(
        self,
        agent_id: str,
        task_handler: TaskHandler,
        agent_card: AgentCard,
        agent_instance: Optional[object] = None,
        endpoint_url: Optional[str] = None,
        gateway_mode: Optional[str] = None,
    ) -> LocalAgentInfo:
        """Register a local agent.

        Args:
            agent_id: Unique agent identifier
            task_handler: A2A TaskHandler for this agent
            agent_card: A2A AgentCard describing capabilities
            agent_instance: Optional original Agent object
            endpoint_url: Optional HTTP endpoint URL
            gateway_mode: Optional gateway mode

        Returns:
            LocalAgentInfo for the registered agent
        """
        info = LocalAgentInfo(
            agent_id=agent_id,
            task_handler=task_handler,
            agent_card=agent_card,
            agent_instance=agent_instance,
            endpoint_url=endpoint_url,
            gateway_mode=gateway_mode,
        )
        self._local_agents[agent_id] = info
        logger.info(f"Registered local agent: {agent_id}")
        return info

    def unregister_local(self, agent_id: str) -> bool:
        """Unregister a local agent.

        Args:
            agent_id: Agent to unregister

        Returns:
            True if agent was found and removed
        """
        if agent_id in self._local_agents:
            del self._local_agents[agent_id]
            logger.info(f"Unregistered local agent: {agent_id}")
            return True
        return False

    def get_local_agent(self, agent_id: str) -> Optional[LocalAgentInfo]:
        """Get information about a local agent.

        Args:
            agent_id: Agent identifier

        Returns:
            LocalAgentInfo if found, None otherwise
        """
        return self._local_agents.get(agent_id)

    def is_local(self, agent_id: str) -> bool:
        """Check if an agent is registered locally.

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent is local
        """
        return agent_id in self._local_agents

    def list_local_agents(self) -> List[LocalAgentInfo]:
        """List all local agents.

        Returns:
            List of LocalAgentInfo for all registered agents
        """
        return list(self._local_agents.values())

    def get_local_agent_ids(self) -> List[str]:
        """Get IDs of all local agents.

        Returns:
            List of agent IDs
        """
        return list(self._local_agents.keys())

    # Remote agent caching

    def cache_remote_agent(
        self,
        agent_id: str,
        agent_card: AgentCard,
        endpoint_url: str,
        gateway_mode: Optional[str] = None,
    ) -> RemoteAgentInfo:
        """Cache information about a remote agent.

        Args:
            agent_id: Agent identifier
            agent_card: Discovered AgentCard
            endpoint_url: Agent's A2A endpoint
            gateway_mode: Optional gateway mode

        Returns:
            RemoteAgentInfo for the cached agent
        """
        info = RemoteAgentInfo(
            agent_id=agent_id,
            agent_card=agent_card,
            endpoint_url=endpoint_url,
            gateway_mode=gateway_mode,
        )
        self._remote_agents[agent_id] = info
        logger.debug(f"Cached remote agent: {agent_id} at {endpoint_url}")
        return info

    def get_remote_agent(self, agent_id: str) -> Optional[RemoteAgentInfo]:
        """Get cached information about a remote agent.

        Args:
            agent_id: Agent identifier

        Returns:
            RemoteAgentInfo if cached, None otherwise
        """
        return self._remote_agents.get(agent_id)

    def is_remote(self, agent_id: str) -> bool:
        """Check if agent is known to be remote.

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent is cached as remote
        """
        return agent_id in self._remote_agents

    def clear_remote_cache(self) -> None:
        """Clear the remote agent cache."""
        self._remote_agents.clear()

    # A2A Client Factory integration

    def set_a2a_client_factory(self, factory: "A2AClientFactory") -> None:
        """Set the A2A client factory reference.

        Args:
            factory: A2AClientFactory instance
        """
        self._a2a_client_factory = factory

    def get_a2a_client_factory(self) -> Optional["A2AClientFactory"]:
        """Get the A2A client factory.

        Returns:
            A2AClientFactory if set, None otherwise
        """
        return self._a2a_client_factory

    # Agent Card lookup

    def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get the AgentCard for any known agent (local or remote).

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCard if agent is known, None otherwise
        """
        local = self._local_agents.get(agent_id)
        if local:
            return local.agent_card

        remote = self._remote_agents.get(agent_id)
        if remote:
            return remote.agent_card

        return None

    def get_endpoint_url(self, agent_id: str) -> Optional[str]:
        """Get the endpoint URL for an agent.

        For local agents, returns their HTTP endpoint if configured.
        For remote agents, returns their cached endpoint.

        Args:
            agent_id: Agent identifier

        Returns:
            Endpoint URL if available, None otherwise
        """
        local = self._local_agents.get(agent_id)
        if local and local.endpoint_url:
            return local.endpoint_url

        remote = self._remote_agents.get(agent_id)
        if remote:
            return remote.endpoint_url

        return None

    def get_gateway_mode(self, agent_id: str) -> Optional[str]:
        """Get the gateway mode for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Gateway mode ("push", "pull") or None
        """
        local = self._local_agents.get(agent_id)
        if local:
            return local.gateway_mode

        remote = self._remote_agents.get(agent_id)
        if remote:
            return remote.gateway_mode

        return None


# Type hint for circular import
if TYPE_CHECKING:
    from aip_sdk.a2a.client_factory import A2AClientFactory

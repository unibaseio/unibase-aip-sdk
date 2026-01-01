"""Local Agent Registry."""

from dataclasses import dataclass
from typing import Dict, List, Optional, TYPE_CHECKING
import logging

from a2a.types import AgentCard

from aip_sdk.a2a.interface import TaskHandler

logger = logging.getLogger(__name__)


@dataclass
class LocalAgentInfo:
    """Information about a locally registered agent."""
    agent_id: str
    task_handler: TaskHandler
    agent_card: AgentCard
    agent_instance: Optional[object] = None
    endpoint_url: Optional[str] = None
    gateway_mode: Optional[str] = None  # "push", "pull", or None for local-only


@dataclass
class RemoteAgentInfo:
    """Information about a discovered remote agent."""
    agent_id: str
    agent_card: AgentCard
    endpoint_url: str
    gateway_mode: Optional[str] = None


class LocalAgentRegistry:
    """Registry for local (in-process) agents."""

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
        """Register a local agent."""
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
        """Unregister a local agent."""
        if agent_id in self._local_agents:
            del self._local_agents[agent_id]
            logger.info(f"Unregistered local agent: {agent_id}")
            return True
        return False

    def get_local_agent(self, agent_id: str) -> Optional[LocalAgentInfo]:
        """Get information about a local agent."""
        return self._local_agents.get(agent_id)

    def is_local(self, agent_id: str) -> bool:
        """Check if an agent is registered locally."""
        return agent_id in self._local_agents

    def list_local_agents(self) -> List[LocalAgentInfo]:
        """List all local agents."""
        return list(self._local_agents.values())

    def get_local_agent_ids(self) -> List[str]:
        """Get IDs of all local agents."""
        return list(self._local_agents.keys())

    # Remote agent caching

    def cache_remote_agent(
        self,
        agent_id: str,
        agent_card: AgentCard,
        endpoint_url: str,
        gateway_mode: Optional[str] = None,
    ) -> RemoteAgentInfo:
        """Cache information about a remote agent."""
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
        """Get cached information about a remote agent."""
        return self._remote_agents.get(agent_id)

    def is_remote(self, agent_id: str) -> bool:
        """Check if agent is known to be remote."""
        return agent_id in self._remote_agents

    def clear_remote_cache(self) -> None:
        """Clear the remote agent cache."""
        self._remote_agents.clear()

    # A2A Client Factory integration

    def set_a2a_client_factory(self, factory: "A2AClientFactory") -> None:
        """Set the A2A client factory reference."""
        self._a2a_client_factory = factory

    def get_a2a_client_factory(self) -> Optional["A2AClientFactory"]:
        """Get the A2A client factory."""
        return self._a2a_client_factory

    # Agent Card lookup

    def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """Get the AgentCard for any known agent (local or remote)."""
        local = self._local_agents.get(agent_id)
        if local:
            return local.agent_card

        remote = self._remote_agents.get(agent_id)
        if remote:
            return remote.agent_card

        return None

    def get_endpoint_url(self, agent_id: str) -> Optional[str]:
        """Get the endpoint URL for an agent."""
        local = self._local_agents.get(agent_id)
        if local and local.endpoint_url:
            return local.endpoint_url

        remote = self._remote_agents.get(agent_id)
        if remote:
            return remote.endpoint_url

        return None

    def get_gateway_mode(self, agent_id: str) -> Optional[str]:
        """Get the gateway mode for an agent."""
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

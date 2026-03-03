"""
LangGraph agent wrapper.

Provides utilities for wrapping LangGraph-based agents
as A2A-compatible services.
"""

import asyncio
from typing import Any, Optional, List

from a2a.types import AgentCard, AgentSkill, AgentCapabilities, Task, Message, Role
from a2a.client.helpers import create_text_message_object

from ..a2a.server import A2AServer
from ..a2a.types import StreamResponse, AgentMessage
from ..utils.logger import get_logger
from ..utils.config import get_default_aip_endpoint

try:
    from aip_sdk.types import CostModel
except ImportError:
    CostModel = None

logger = get_logger("wrappers.langgraph")


class LangGraphWrapper:
    """
    Wrapper for LangGraph-based agents.

    Wraps a LangGraph StateGraph or compiled graph as an A2A service,
    handling state management and streaming.
    """

    def __init__(
        self,
        graph: Any,
        name: str,
        *,
        input_key: str = "message",
        output_key: str = "output",
        description: str = None,
        skills: List[AgentSkill] = None,
        version: str = "1.0.0",
    ):
        """
        Initialize LangGraph wrapper.

        Args:
            graph: The compiled LangGraph graph
            name: Agent name
            input_key: Key for input in state dict
            output_key: Key for output in state dict
            description: Agent description
            skills: List of AgentSkill definitions
            version: Agent version
        """
        self.graph = graph
        self.name = name
        self.input_key = input_key
        self.output_key = output_key
        self.description = description or f"{name} LangGraph agent"
        self.version = version

        # Create default skill if not provided
        if skills is None:
            skill_id = name.lower().replace(" ", "_")
            self.skills = [
                AgentSkill(
                    id=skill_id,
                    name=name,
                    description=self.description,
                    tags=["langgraph"],
                )
            ]
        else:
            self.skills = skills

    async def invoke(self, message: str, session_id: str = "default") -> str:
        """
        Invoke the LangGraph graph.

        Args:
            message: Input message
            session_id: Session ID for state management

        Returns:
            Output string from the graph
        """
        # Build initial state
        initial_state = {self.input_key: message}

        # Invoke the graph
        if asyncio.iscoroutinefunction(self.graph.invoke):
            result = await self.graph.invoke(initial_state)
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self.graph.invoke, initial_state
            )

        # Extract output
        output = result.get(self.output_key, str(result))
        return output if isinstance(output, str) else str(output)

    async def _task_handler(
        self, task: Task, message: Message
    ):
        """A2A task handler."""
        # Parse message
        agent_message = AgentMessage.from_a2a_message(message)
        input_text = agent_message.intent

        logger.debug(
            f"LangGraph processing: {input_text[:100]}",
            extra={
                "agent": self.name,
                "run_id": agent_message.context.run_id,
            },
        )

        # Invoke graph
        result = await self.invoke(
            input_text,
            session_id=agent_message.context.run_id or "default",
        )

        # Create response
        response_msg = create_text_message_object(Role.agent, result)
        yield StreamResponse(message=response_msg)

    def to_server(
        self,
        port: int = 8000,
        host: str = "0.0.0.0",
        cost_model: Any = None,
        user_id: str = None,
        aip_endpoint: str = None,
        auto_register: bool = True,
        endpoint_url: str = None,
    ) -> A2AServer:
        """
        Create an A2A server for this wrapped agent.

        Args:
            port: Port to listen on
            host: Host to bind to
            cost_model: Pricing model
            user_id: AIP user ID for registration
            aip_endpoint: AIP platform endpoint
            auto_register: Whether to auto-register

        Returns:
            A2AServer instance
        """
        # Build agent card
        # Priority for discovery URL: endpoint_url > local host:port
        discovery_url = endpoint_url or f"http://{host}:{port}"

        agent_card = AgentCard(
            name=self.name,
            description=self.description,
            url=discovery_url,
            version=self.version,
            skills=self.skills,
            capabilities=AgentCapabilities(streaming=True),
            default_input_modes=["text/plain", "application/json"],
            default_output_modes=["text/plain", "application/json"],
        )

        # Build registration config
        registration_config = None
        if user_id and auto_register:
            handle = self.name.lower().replace(" ", "-")
            resolved_cost = cost_model
            if resolved_cost is None and CostModel is not None:
                resolved_cost = CostModel(base_call_fee=0.001)

            registration_config = {
                "user_id": user_id,
                "aip_endpoint": aip_endpoint or get_default_aip_endpoint(),
                "handle": handle,
                "name": self.name,
                "description": self.description,
                "skills": [
                    {"id": s.id, "name": s.name, "description": s.description}
                    for s in self.skills
                ],
                "cost_model": resolved_cost.to_dict() if resolved_cost else None,
                "endpoint_url": endpoint_url,
            }

        return A2AServer(
            agent_card=agent_card,
            task_handler=self._task_handler,
            host=host,
            port=port,
            registration_config=registration_config,
        )

    async def serve(self, port: int = 8000, host: str = "0.0.0.0", **kwargs):
        """Start serving as A2A service."""
        server = self.to_server(port=port, host=host, **kwargs)
        await server.run()

    def serve_sync(self, port: int = 8000, host: str = "0.0.0.0", **kwargs):
        """Start serving synchronously."""
        asyncio.run(self.serve(port=port, host=host, **kwargs))


def expose_langgraph_as_a2a(
    graph: Any,
    name: str,
    *,
    port: int = 8000,
    host: str = "0.0.0.0",
    input_key: str = "message",
    output_key: str = "output",
    description: str = None,
    skills: List[AgentSkill] = None,
    version: str = "1.0.0",
    cost_model: Any = None,
    user_id: str = None,
    aip_endpoint: str = None,
    auto_register: bool = True,
    endpoint_url: str = None,
) -> A2AServer:
    """
    Expose a LangGraph graph as an A2A service.

    Args:
        graph: The compiled LangGraph graph
        name: Agent name
        port: Port to listen on
        host: Host to bind to
        input_key: Key for input in state dict
        output_key: Key for output in state dict
        description: Agent description
        skills: List of AgentSkill definitions
        version: Agent version
        cost_model: Pricing model
        user_id: AIP user ID for registration
        aip_endpoint: AIP platform endpoint
        auto_register: Whether to auto-register

    Returns:
        A2AServer instance ready to run
    """
    wrapper = LangGraphWrapper(
        graph=graph,
        name=name,
        input_key=input_key,
        output_key=output_key,
        description=description,
        skills=skills,
        version=version,
    )

    return wrapper.to_server(
        port=port,
        host=host,
        cost_model=cost_model,
        user_id=user_id,
        aip_endpoint=aip_endpoint,
        auto_register=auto_register,
        endpoint_url=endpoint_url,
    )

"""
Google ADK agent wrapper.

Provides utilities for wrapping Google ADK (Agent Development Kit)
agents as A2A-compatible services.
"""

import asyncio
import uuid
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

logger = get_logger("wrappers.adk")


class ADKWrapper:
    """
    Wrapper for Google ADK-based agents.

    Wraps an ADK LlmAgent with Runner as an A2A service,
    handling session management and response extraction.
    """

    def __init__(
        self,
        adk_agent: Any,
        runner: Any = None,
        name: str = None,
        *,
        description: str = None,
        skills: List[AgentSkill] = None,
        version: str = "1.0.0",
        user_id: str = "remote_agent",
    ):
        """
        Initialize ADK wrapper.

        Args:
            adk_agent: The ADK LlmAgent instance
            runner: Optional pre-configured Runner
            name: Agent name (defaults to adk_agent.name)
            description: Agent description
            skills: List of AgentSkill definitions
            version: Agent version
            user_id: User ID for ADK sessions
        """
        self.adk_agent = adk_agent
        self.name = name or getattr(adk_agent, "name", "ADKAgent")
        self.description = description or getattr(
            adk_agent, "description", f"{self.name} ADK agent"
        )
        self.version = version
        self.adk_user_id = user_id

        # Create runner if not provided
        if runner is not None:
            self.runner = runner
        else:
            self.runner = self._create_runner()

        # Create default skill if not provided
        if skills is None:
            skill_id = self.name.lower().replace(" ", "_")
            self.skills = [
                AgentSkill(
                    id=skill_id,
                    name=self.name,
                    description=self.description,
                    tags=["adk", "gemini"],
                )
            ]
        else:
            self.skills = skills

    def _create_runner(self) -> Any:
        """Create an ADK Runner with in-memory services."""
        try:
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
            from google.adk.artifacts import InMemoryArtifactService

            return Runner(
                app_name=self.adk_agent.name,
                agent=self.adk_agent,
                artifact_service=InMemoryArtifactService(),
                session_service=InMemorySessionService(),
                memory_service=InMemoryMemoryService(),
            )
        except ImportError:
            logger.warning("Google ADK not installed, runner creation skipped")
            return None

    async def invoke(self, message: str, session_id: str = None) -> str:
        """
        Invoke the ADK agent.

        Args:
            message: Input message
            session_id: Session ID (auto-generated if not provided)

        Returns:
            Output string from the agent
        """
        if self.runner is None:
            raise RuntimeError("ADK Runner not available")

        # Generate session ID if not provided
        if session_id is None:
            session_id = f"session_{uuid.uuid4().hex[:8]}"

        try:
            from google.genai import types

            # Get or create session
            session = await self.runner.session_service.get_session(
                app_name=self.adk_agent.name,
                user_id=self.adk_user_id,
                session_id=session_id,
            )

            if session is None:
                session = await self.runner.session_service.create_session(
                    app_name=self.adk_agent.name,
                    user_id=self.adk_user_id,
                    state={},
                    session_id=session_id,
                )

            # Create content
            content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=message)],
            )

            # Run agent
            response_text = ""
            async for event in self.runner.run_async(
                user_id=self.adk_user_id,
                session_id=session.id,
                new_message=content,
            ):
                if event.is_final_response():
                    if (
                        event.content
                        and event.content.parts
                        and event.content.parts[0].text
                    ):
                        response_text = "\n".join(
                            [p.text for p in event.content.parts if p.text]
                        )
                    break

            return response_text

        except ImportError:
            raise RuntimeError("Google ADK not installed")

    async def _task_handler(
        self, task: Task, message: Message
    ):
        """A2A task handler."""
        # Parse message
        agent_message = AgentMessage.from_a2a_message(message)
        input_text = agent_message.intent

        logger.debug(
            f"ADK processing: {input_text[:100]}",
            extra={
                "agent": self.name,
                "run_id": agent_message.context.run_id,
            },
        )

        # Invoke agent
        result = await self.invoke(
            input_text,
            session_id=agent_message.context.run_id,
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


def expose_adk_as_a2a(
    adk_agent: Any,
    name: str = None,
    *,
    runner: Any = None,
    port: int = 8000,
    host: str = "0.0.0.0",
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
    Expose a Google ADK agent as an A2A service.

    Args:
        adk_agent: The ADK LlmAgent instance
        name: Agent name (defaults to adk_agent.name)
        runner: Optional pre-configured Runner
        port: Port to listen on
        host: Host to bind to
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
    wrapper = ADKWrapper(
        adk_agent=adk_agent,
        runner=runner,
        name=name,
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

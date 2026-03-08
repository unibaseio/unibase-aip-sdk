"""Generic Agent Wrapper."""

from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    List,
    AsyncIterator,
    Awaitable,
    Union,
)
import json
import asyncio
import inspect
import os

# Import directly from Google A2A SDK
from a2a.types import (
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    Message,
    Role,
    Task,
)
from aip_sdk.types import AgentCard, AgentSkillCard, AgentCapabilities, AgentProvider, AgentService
from a2a.utils.message import get_message_text
from a2a.client.helpers import create_text_message_object

# Import Unibase extensions
from aip_sdk.a2a.server import A2AServer
from aip_sdk.a2a.types import StreamResponse, AgentMessage
from aip_sdk.utils.logger import get_logger
from aip_sdk.utils.config import get_default_aip_endpoint

# Import CostModel from SDK
from aip_sdk.types import CostModel

logger = get_logger("wrappers.generic")


def parse_agent_message(message: Message) -> AgentMessage:
    """Parse an A2A Message into AgentMessage format."""

    print(f"DEBUG parse_agent_message: message type = {type(message)}")
    print(f"DEBUG parse_agent_message: hasattr parts = {hasattr(message, 'parts')}")
    if hasattr(message, 'parts'):
        print(f"DEBUG parse_agent_message: message.parts type = {type(message.parts)}")
        print(f"DEBUG parse_agent_message: message.parts length = {len(message.parts) if message.parts else 0}")

    text_parts = []

    # message.parts should be a list of Part objects (RootModel wrappers)
    # Each Part.root gives us the actual TextPart | FilePart | DataPart
    if hasattr(message, 'parts') and message.parts:
        for i, part in enumerate(message.parts):
            print(f"DEBUG parse_agent_message: part[{i}] type = {type(part)}")
            print(f"DEBUG parse_agent_message: part[{i}] hasattr root = {hasattr(part, 'root')}")

            # Part is a RootModel, access .root to get the actual part object
            if hasattr(part, 'root'):
                actual_part = part.root
                print(f"DEBUG parse_agent_message: actual_part type = {type(actual_part)}")
            else:
                actual_part = part
                print(f"DEBUG parse_agent_message: using part directly, type = {type(actual_part)}")

            # Check if it's a TextPart by checking for 'text' attribute and 'kind' == 'text'
            print(f"DEBUG parse_agent_message: hasattr kind = {hasattr(actual_part, 'kind')}")
            if hasattr(actual_part, 'kind'):
                print(f"DEBUG parse_agent_message: actual_part.kind = {actual_part.kind}")

            if hasattr(actual_part, 'kind') and actual_part.kind == 'text':
                print(f"DEBUG parse_agent_message: hasattr text = {hasattr(actual_part, 'text')}")
                if hasattr(actual_part, 'text'):
                    text_val = actual_part.text
                    print(f"DEBUG parse_agent_message: text value = {text_val}")
                    print(f"DEBUG parse_agent_message: text type = {type(text_val)}")
                    if isinstance(text_val, str):
                        text_parts.append(text_val)
                        print(f"DEBUG parse_agent_message: appended text to text_parts")

    text = " ".join(text_parts)
    print(f"DEBUG parse_agent_message: final extracted text = '{text}'")
    
    # Logic similar to AgentMessage.from_a2a_message
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if "intent" in data and "context" in data:
                return AgentMessage.from_dict(data)
                
            if "task" in data:
                # Handle task payload format if present
                # (Simplified version of what logic exists in aip_sdk)
                pass
                
            # If valid JSON but not a standard envelope, treat as structured data?
            # Or just fall through to text intent if it's not a special format.
    except (json.JSONDecodeError, TypeError):
        pass

    # Default: Treat text as intent
    # Use message_id as run_id if available, to ensure we have some context
    from aip_sdk.types import MessageContext
    
    return AgentMessage(
        intent=text,
        context=MessageContext(
            run_id=getattr(message, "message_id", "") or "",
            caller_id="unknown"
        )
    )


# Type aliases
SyncHandler = Callable[[str], str]
AsyncHandler = Callable[[str], Awaitable[str]]
Handler = Union[SyncHandler, AsyncHandler]

SyncStreamHandler = Callable[[str], List[str]]
AsyncStreamHandler = Callable[[str], AsyncIterator[str]]
StreamHandler = Union[SyncStreamHandler, AsyncStreamHandler]


def _create_task_handler(
    handler: Handler,
    streaming: bool = False,
    raw_response: bool = False,
) -> Callable[[Task, Message], AsyncIterator[StreamResponse]]:
    """Create an A2A task handler from a simple function.

    The handler receives plain text extracted from the A2A Message.
    The wrapper handles all Message format conversions.
    """

    is_async = asyncio.iscoroutinefunction(handler)
    is_async_gen = inspect.isasyncgenfunction(handler)

    # Check for user_id parameter in handler
    sig = inspect.signature(handler)
    needs_user_id = "user_id" in sig.parameters

    async def task_handler(task: Task, message: Message) -> AsyncIterator[StreamResponse]:
        # Extract text directly using A2A SDK utility
        input_text = get_message_text(message)

        # Log for debugging
        logger.debug(f"Processing request: {input_text[:100] if input_text else 'empty'}")

        # Prepare arguments
        args = [input_text]
        if needs_user_id:
            # Extract user_id from message metadata or context
            # A2A protocol doesn't have a standard user_id field in Message,
            # but we can try to extract from metadata or caller info
            user_id = "anonymous"
            if message.metadata:
                user_id = message.metadata.get("user_id", user_id)
            elif hasattr(message, "context") and message.context:
                 # Try to use caller as user_id if available
                 if hasattr(message.context, "caller") and message.context.caller:
                     user_id = message.context.caller
            
            args.append(user_id)

        if streaming:
            # Streaming handler
            if is_async_gen:
                async for chunk in handler(*args):
                    if raw_response:
                         yield StreamResponse(raw_content=chunk)
                    else:
                        response_msg = create_text_message_object(Role.agent, chunk)
                        yield StreamResponse(message=response_msg)
            elif is_async:
                result = await handler(*args)
                for chunk in result:
                     if raw_response:
                         yield StreamResponse(raw_content=chunk)
                     else:
                         response_msg = create_text_message_object(Role.agent, chunk)
                         yield StreamResponse(message=response_msg)
            else:
                for chunk in handler(*args):
                    if raw_response:
                        yield StreamResponse(raw_content=chunk)
                    else:
                        response_msg = create_text_message_object(Role.agent, chunk)
                        yield StreamResponse(message=response_msg)
        else:
            # Non-streaming handler
            if is_async:
                result = await handler(*args)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, handler, *args)

            if raw_response:
                yield StreamResponse(raw_content=str(result))
            else:
                response_msg = create_text_message_object(Role.agent, str(result))
                yield StreamResponse(message=response_msg)

    return task_handler


def expose_as_a2a(
    name: str,
    handler: Handler,
    *,
    port: int = 8000,
    host: str = "0.0.0.0",
    description: str = None,
    skills: List[AgentSkillCard] = None,
    streaming: bool = False,
    raw_response: bool = False, 
    version: str = "1.0.0",
    # Account integration
    user_id: str = None,
    aip_endpoint: str = None,
    gateway_url: str = None,
    handle: str = None,
    auto_register: bool = True,
    # Pricing via cost_model
    cost_model: CostModel = None,
    currency: str = "USD",
    endpoint_url: str = None,
    metadata: Dict[str, Any] = None,
    chain_id: int = 97,
    **kwargs,
) -> A2AServer:
    """Expose ANY callable as an A2A-compatible agent service.

    Args:
        name: Agent name
        handler: The callable to expose (sync or async function)
        port: Port to listen on (default: 8000)
        host: Host to bind to (default: 0.0.0.0)
        description: Agent description
        skills: List of AgentSkill definitions
        streaming: Enable streaming responses
        raw_response: If True, handler output is sent directly as SSE data without JSON-RPC wrapping
        version: Agent version string
        user_id: AIP platform user ID for registration
        aip_endpoint: AIP platform endpoint URL
        handle: Agent handle (auto-generated from name if not provided)
        auto_register: Whether to auto-register with AIP platform
        cost_model: Pricing model (use CostModel(base_call_fee=0.05) for $0.05/call)
        currency: Currency for pricing (default: USD)
        chain_id: Target blockchain ID for registration (default: 97)
        **kwargs: Additional arguments passed to AgentCard

    Returns:
        A2AServer instance ready to run

    Example:
        server = expose_as_a2a(
            "Calculator",
            my_handler,
            cost_model=CostModel(base_call_fee=0.05),  # $0.05 per call
            user_id="user:0x123...",
        )
    """
    # Create default description
    if description is None:
        description = f"{name} agent"

    # Create default skill if not provided
    if skills is None:
        skill_id = name.lower().replace(" ", "_")
        skills = [
            AgentSkillCard(
                id=skill_id,
                name=name,
                description=description,
                tags=[],
            )
        ]

    # Generate handle from name if not provided
    if handle is None:
        handle = name.lower().replace(" ", ".").replace("_", ".")

    # Build Agent Card with Google A2A types
    # Priority for discovery URL: endpoint_url > local host:port
    discovery_url = endpoint_url or f"http://{host}:{port}"

    agent_card = AgentCard(
        name=name,
        description=description,
        url=discovery_url,
        version=version,
        skills=skills,
        capabilities=AgentCapabilities(streaming=streaming),
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["text/plain", "application/json"],
        **kwargs,
    )

    # Create task handler
    task_handler = _create_task_handler(handler, streaming=streaming, raw_response=raw_response)

    # Resolve account integration settings
    resolved_user_id = user_id or os.getenv("AIP_USER_ID")
    resolved_aip_endpoint = aip_endpoint or get_default_aip_endpoint()

    # Use default cost_model if not provided
    resolved_cost_model = cost_model or CostModel(base_call_fee=0.001)

    # Create registration config if user_id is provided
    # Config is needed for both registration AND Gateway polling
    registration_config = None
    if resolved_user_id and (auto_register or gateway_url):
        registration_config = {
            "user_id": resolved_user_id,
            "aip_endpoint": resolved_aip_endpoint,
            "gateway_url": gateway_url,
            "handle": handle,
            "name": name,
            "description": description,
            "skills": [{"id": s.id, "name": s.name, "description": s.description} for s in skills],
            "cost_model": resolved_cost_model.to_dict(),
            "currency": currency,
            "endpoint_url": endpoint_url,
            "metadata": metadata or {},
            "chain_id": chain_id,
        }

    # Create and return server
    return A2AServer(
        agent_card=agent_card,
        task_handler=task_handler,
        host=host,
        port=port,
        registration_config=registration_config,
        auto_register=auto_register,
    )


class AgentWrapper:
    """Wrapper for class-based agents."""

    def __init__(
        self,
        agent: Any,
        name: str,
        *,
        method: str = None,
        skill_methods: dict[str, str] = None,
        description: str = None,
        version: str = "1.0.0",
        endpoint_url: str = None,
        metadata: Dict[str, Any] = None,
    ):
        """Initialize agent wrapper."""
        self.agent = agent
        self.name = name
        self.description = description or f"{name} agent"
        self.version = version
        self.endpoint_url = endpoint_url
        self.metadata = metadata or {}

        if method and skill_methods:
            raise ValueError("Cannot specify both 'method' and 'skill_methods'")

        if skill_methods:
            self.skill_methods = skill_methods
        elif method:
            skill_id = name.lower().replace(" ", "_")
            self.skill_methods = {skill_id: method}
        else:
            # Auto-detect public methods
            self.skill_methods = self._auto_detect_methods()

        self._validate_methods()

    def _auto_detect_methods(self) -> dict[str, str]:
        """Auto-detect public methods that could be skills."""
        methods = {}
        for attr_name in dir(self.agent):
            if attr_name.startswith("_"):
                continue
            attr = getattr(self.agent, attr_name)
            if callable(attr) and not isinstance(attr, type):
                # Check if it looks like a handler (takes string, returns string)
                sig = inspect.signature(attr)
                params = list(sig.parameters.values())
                # Accept methods with 1 required param (besides self)
                required_params = [p for p in params if p.default is inspect.Parameter.empty]
                if len(required_params) <= 1:
                    methods[attr_name] = attr_name
        return methods

    def _validate_methods(self):
        """Validate that all specified methods exist."""
        for skill_id, method_name in self.skill_methods.items():
            if not hasattr(self.agent, method_name):
                raise ValueError(
                    f"Agent has no method '{method_name}' for skill '{skill_id}'"
                )

    def _build_skills(self) -> List[AgentSkillCard]:
        """Build AgentSkillCard list from skill_methods."""
        skills = []
        for skill_id, method_name in self.skill_methods.items():
            method = getattr(self.agent, method_name)
            doc = method.__doc__ or f"{method_name} skill"
            skills.append(
                AgentSkillCard(
                    id=skill_id,
                    name=method_name.replace("_", " ").title(),
                    description=doc.strip(),
                    tags=[],
                )
            )
        return skills

    async def _handle_task(self, task: Task, message: Message) -> AsyncIterator[StreamResponse]:
        """Route task to appropriate method."""
        # Parse message using new AgentMessage format
        agent_message = AgentMessage.from_a2a_message(message)
        input_text = agent_message.intent

        # Log context for debugging
        logger.debug(
            "AgentWrapper processing request",
            extra={
                "agent": self.name,
                "intent": input_text[:100] if input_text else None,
                "run_id": agent_message.context.run_id,
                "caller": agent_message.context.caller_id,
            }
        )

        # For single-skill agents, use the only method
        if len(self.skill_methods) == 1:
            method_name = list(self.skill_methods.values())[0]
        else:
            # Check if hints suggest a specific skill
            if agent_message.hints and agent_message.hints.suggested_task:
                suggested = agent_message.hints.suggested_task
                if suggested in self.skill_methods:
                    method_name = self.skill_methods[suggested]
                else:
                    method_name = list(self.skill_methods.values())[0]
            else:
                method_name = list(self.skill_methods.values())[0]

        method = getattr(self.agent, method_name)

        # Call the method
        if asyncio.iscoroutinefunction(method):
            result = await method(input_text)
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, method, input_text)

        response_msg = create_text_message_object(Role.agent, str(result))
        yield StreamResponse(message=response_msg)

    def to_server(self, port: int = 8000, host: str = "0.0.0.0") -> A2AServer:
        """Create an A2AServer for this wrapped agent."""
        # Priority for discovery URL: endpoint_url > local host:port
        discovery_url = self.endpoint_url or f"http://{host}:{port}"

        agent_card = AgentCard(
            name=self.name,
            description=self.description,
            url=discovery_url,
            version=self.version,
            provider=AgentProvider(
                organization="AgentWrapper",
                url=discovery_url
            ),
            skills=self._build_skills(),
            services=[
                AgentService(name="A2A", endpoint=f"{discovery_url}/.well-known/agent-card.json", a2aSkills=[s.name for s in self._build_skills()]),
                AgentService(name="web", endpoint=discovery_url)
            ],
            capabilities=AgentCapabilities(),
            defaultInputModes=["text/plain", "application/json"],
            defaultOutputModes=["text/plain", "application/json"],
            metadata=self.metadata,
        )

        return A2AServer(
            agent_card=agent_card,
            task_handler=self._handle_task,
            host=host,
            port=port,
        )

    async def serve(self, port: int = 8000, host: str = "0.0.0.0"):
        """Start serving the agent as an A2A service."""
        server = self.to_server(port=port, host=host)
        await server.run()

    def serve_sync(self, port: int = 8000, host: str = "0.0.0.0"):
        """Start serving the agent synchronously."""
        asyncio.run(self.serve(port=port, host=host))


def wrap_agent(
    agent: Any,
    name: str = None,
    method: str = None,
    **kwargs,
) -> AgentWrapper:
    """Convenience function to wrap an agent instance."""
    if name is None:
        name = agent.__class__.__name__

    return AgentWrapper(agent=agent, name=name, method=method, **kwargs)

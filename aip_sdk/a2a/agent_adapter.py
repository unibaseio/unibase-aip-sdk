"""A2A Agent Adapter - Adapts existing Agents to A2A protocol.

This adapter wraps existing AIP Agent implementations to work with the
A2A protocol, converting between the perform_task interface and A2A
Task/Message format.

The adapter handles:
- Converting A2A Message to TaskSpec for perform_task
- Converting TaskResult to A2A StreamResponse
- Creating proper AgentContext for agent execution
- Generating A2A AgentCard from AgentConfig
"""

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional
import json
import logging
import uuid

from unibase_agent_sdk.a2a.types import (
    Task as A2ATask,
    TaskState,
    TaskStatus,
    Message,
    StreamResponse,
    TaskStatusUpdateEvent,
    Artifact,
    TextPart,
    AgentCard,
    Skill,
    Provider,
    Role,
)

from aip_sdk.types import Task as SDKTask, TaskResult, AgentContext

if TYPE_CHECKING:
    from aip_sdk.a2a.client_factory import A2AClientFactory

logger = logging.getLogger(__name__)


def extract_text_from_message(message: Message) -> str:
    """Extract plain text content from an A2A Message.

    Args:
        message: A2A Message with parts

    Returns:
        Concatenated text from all TextParts
    """
    texts = []
    for part in message.parts:
        if hasattr(part, "text"):
            texts.append(part.text)
    return " ".join(texts)


def extract_payload_from_message(message: Message) -> Dict[str, Any]:
    """Extract structured payload from an A2A Message.

    Tries to parse JSON from the message text, or returns
    the text wrapped in a 'query' field.

    Args:
        message: A2A Message

    Returns:
        Dict payload suitable for perform_task
    """
    text = extract_text_from_message(message)

    # Try to parse as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Check metadata for structured payload
    if message.metadata and "payload" in message.metadata:
        return message.metadata["payload"]

    # Return as query
    return {"query": text}


def task_result_to_message(result: TaskResult) -> Message:
    """Convert a TaskResult to an A2A Message.

    Args:
        result: TaskResult from perform_task

    Returns:
        A2A Message with result content
    """
    # Build response text
    if result.success:
        if result.summary:
            text = result.summary
        else:
            text = json.dumps(result.output, indent=2)
    else:
        text = f"Error: {result.error or 'Unknown error'}"

    return Message.agent(text)


def agent_config_to_card(
    agent_id: str,
    config: Any,
    endpoint_url: Optional[str] = None,
) -> AgentCard:
    """Convert an AgentConfig to an A2A AgentCard.

    Args:
        agent_id: Agent identifier
        config: AgentConfig object
        endpoint_url: Optional HTTP endpoint URL

    Returns:
        A2A AgentCard
    """
    # Build skills list
    skills = []
    if hasattr(config, "skills"):
        for skill in config.skills:
            # Build input/output schema from SkillConfig
            input_schema = {}
            output_schema = {}

            if hasattr(skill, "inputs"):
                properties = {}
                required = []
                for inp in skill.inputs:
                    properties[inp.name] = {
                        "type": inp.field_type,
                        "description": inp.description,
                    }
                    if inp.required:
                        required.append(inp.name)
                input_schema = {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }

            if hasattr(skill, "outputs"):
                properties = {}
                for out in skill.outputs:
                    properties[out.name] = {
                        "type": out.field_type,
                        "description": out.description,
                    }
                output_schema = {
                    "type": "object",
                    "properties": properties,
                }

            skills.append(
                Skill(
                    id=skill.name.lower().replace(" ", "_"),
                    name=skill.name,
                    description=skill.description,
                    input_modes=["text", "text/plain", "application/json"],
                    output_modes=["text", "text/plain", "application/json"],
                )
            )

    # Build capabilities list
    capabilities = []
    if hasattr(config, "capabilities"):
        # Simple string capabilities
        capabilities = config.capabilities

    # Build URL
    url = endpoint_url or f"local://{agent_id}"

    return AgentCard(
        name=config.name if hasattr(config, "name") else agent_id,
        description=config.description if hasattr(config, "description") else "",
        url=url,
        version="1.0.0",
        provider=Provider(
            organization="AIP",
            url="https://aip.local",
        ),
        skills=skills,
        default_input_modes=["text", "application/json"],
        default_output_modes=["text", "application/json"],
    )


class A2AAgentAdapter:
    """Adapts an existing Agent to A2A protocol.

    This adapter wraps an Agent that uses perform_task(task, context)
    and exposes it as an A2A TaskHandler that accepts Task objects
    and yields StreamResponse events.

    Features:
    - Converts A2A Messages to TaskSpec format
    - Converts TaskResult to A2A StreamResponse
    - Creates AgentContext with A2A-based inter-agent calls
    - Generates AgentCard from AgentConfig

    Example:
        agent = MyAgent()
        adapter = A2AAgentAdapter(agent, client_factory)

        # Register with the A2A system
        factory.register_local_agent(
            agent_id=agent.agent_id,
            task_handler=adapter.handle_task,
            agent_card=adapter.agent_card,
        )
    """

    def __init__(
        self,
        agent: Any,
        client_factory: Optional["A2AClientFactory"] = None,
        *,
        endpoint_url: Optional[str] = None,
    ):
        """Initialize the adapter.

        Args:
            agent: The Agent to adapt
            client_factory: A2AClientFactory for inter-agent calls
            endpoint_url: Optional HTTP endpoint URL for the agent
        """
        self._agent = agent
        self._client_factory = client_factory
        self._endpoint_url = endpoint_url

        # Generate agent card
        if hasattr(agent, 'config') and agent.config:
            self._agent_card = agent_config_to_card(
                agent.agent_id,
                agent.config,
                endpoint_url,
            )
        else:
            # Minimal card for agents without config
            self._agent_card = AgentCard(
                name=agent.agent_id,
                description="",
                url=endpoint_url or f"local://{agent.agent_id}",
                version="1.0.0",
            )

    @property
    def agent(self) -> Any:
        """Get the wrapped agent."""
        return self._agent

    @property
    def agent_card(self) -> AgentCard:
        """Get the A2A AgentCard for this agent."""
        return self._agent_card

    def _create_context(
        self,
        task: A2ATask,
        run_id: str,
    ) -> AgentContext:
        """Create an AgentContext for the task.

        Args:
            task: A2A Task being processed
            run_id: Run identifier for event correlation

        Returns:
            AgentContext for use in perform_task
        """
        factory = self._client_factory

        async def invoke_agent(
            agent_id: str,
            sub_task: Any,
            reason: str = "",
        ) -> TaskResult:
            """Invoke another agent via A2A."""
            if not factory:
                return TaskResult.error_result(
                    "Agent invocation not available (no client factory)"
                )

            # Convert task to A2A message
            if isinstance(sub_task, dict):
                payload = sub_task
            elif hasattr(sub_task, "payload"):
                payload = sub_task.payload
            else:
                payload = {"task": str(sub_task)}

            message = Message.user(json.dumps(payload))

            # Import here to avoid circular import
            from aip_sdk.a2a.envelope import AIPContext

            # Create AIP context for the call
            aip_context = AIPContext(
                run_id=run_id,
                caller_agent=self._agent.agent_id,
                caller_chain=[],
            )

            try:
                result_task = await factory.send_task(
                    agent_id=agent_id,
                    message=message,
                    context_id=task.context_id,
                    aip_context=aip_context,
                )

                # Convert A2A Task to TaskResult
                if result_task.status.state == TaskState.COMPLETED:
                    # Get response from history or artifacts
                    output = {}
                    summary = ""

                    if result_task.history:
                        last_msg = result_task.history[-1]
                        if last_msg.role == Role.AGENT:
                            summary = extract_text_from_message(last_msg)
                            try:
                                output = json.loads(summary)
                            except json.JSONDecodeError:
                                output = {"response": summary}

                    if result_task.artifacts:
                        for artifact in result_task.artifacts:
                            for part in artifact.parts:
                                if hasattr(part, "text"):
                                    output["artifact_text"] = part.text
                                if hasattr(part, "data"):
                                    output["artifact_data"] = part.data

                    return TaskResult.success_result(
                        output=output,
                        summary=summary,
                    )
                else:
                    error_msg = "Task failed"
                    if result_task.status.message:
                        error_msg = extract_text_from_message(result_task.status.message)
                    return TaskResult.error_result(error_msg)

            except Exception as e:
                logger.exception(f"Error invoking agent {agent_id}")
                return TaskResult.error_result(str(e))

        def emit_event(event: Dict[str, Any]) -> None:
            """Emit an event."""
            logger.debug(f"Event from {self._agent.agent_id}: {event}")

        async def send_message(msg: Any) -> None:
            """Send a message (not implemented for A2A adapter)."""
            logger.debug(f"Message from {self._agent.agent_id}: {msg}")

        async def receive_message(
            topic: Optional[str] = None,
            timeout: Optional[float] = None,
        ) -> Any:
            """Receive a message (not implemented for A2A adapter)."""
            return None

        def memory_read(scope: str) -> Dict[str, Any]:
            """Read from memory (stub implementation)."""
            logger.debug(f"Memory read from scope: {scope}")
            return {}

        def memory_write(
            scope: str,
            data: Dict[str, Any],
            description: str = "",
        ) -> None:
            """Write to memory (stub implementation)."""
            logger.debug(f"Memory write to scope: {scope}")

        return AgentContext(
            invoke_agent=invoke_agent,
            emit_event=emit_event,
            send_message=send_message,
            receive_message=receive_message,
            memory_read=memory_read,
            memory_write=memory_write,
        )

    async def handle_task(
        self,
        task: A2ATask,
    ) -> AsyncGenerator[StreamResponse, None]:
        """Handle an A2A Task by calling the wrapped agent.

        This is the TaskHandler interface for A2A.

        Args:
            task: A2A Task to process

        Yields:
            StreamResponse events
        """
        run_id = task.context_id or str(uuid.uuid4())

        # Emit initial working status
        yield StreamResponse(
            status_update=TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.WORKING),
            )
        )

        try:
            # Get the last user message from history
            user_message = None
            for msg in reversed(task.history):
                if msg.role == Role.USER:
                    user_message = msg
                    break

            if not user_message:
                # No user message, create error response
                yield StreamResponse(
                    status_update=TaskStatusUpdateEvent(
                        task_id=task.id,
                        context_id=task.context_id,
                        status=TaskStatus(
                            state=TaskState.FAILED,
                            message=Message.agent("No user message in task"),
                        ),
                        final=True,
                    )
                )
                return

            # Extract payload from message
            payload = extract_payload_from_message(user_message)

            # Create SDK Task
            sdk_task = SDKTask(
                task_id=task.id,
                name=payload.get("task_name", "execute"),
                description=payload.get("query", ""),
                payload=payload,
            )

            # Create context
            context = self._create_context(task, run_id)

            # Call the agent's perform_task
            result = await self._agent.perform_task(sdk_task, context)

            # Convert result to A2A response
            response_message = task_result_to_message(result)

            # Yield the response message
            yield StreamResponse(message=response_message)

            # If there's structured output, yield as artifact
            if result.output and result.success:
                yield StreamResponse(
                    artifact_update=TaskStatusUpdateEvent(
                        task_id=task.id,
                        context_id=task.context_id,
                        artifact=Artifact(
                            parts=[
                                TextPart(text=json.dumps(result.output, indent=2))
                            ],
                            index=0,
                            last_chunk=True,
                        ),
                    )
                )

            # Yield completion status
            final_state = TaskState.COMPLETED if result.success else TaskState.FAILED
            status_message = None if result.success else Message.agent(result.error or "Unknown error")

            yield StreamResponse(
                status_update=TaskStatusUpdateEvent(
                    task_id=task.id,
                    context_id=task.context_id,
                    status=TaskStatus(
                        state=final_state,
                        message=status_message,
                    ),
                    final=True,
                )
            )

        except Exception as e:
            logger.exception(f"Error handling task {task.id}")
            yield StreamResponse(
                status_update=TaskStatusUpdateEvent(
                    task_id=task.id,
                    context_id=task.context_id,
                    status=TaskStatus(
                        state=TaskState.FAILED,
                        message=Message.agent(str(e)),
                    ),
                    final=True,
                )
            )


def adapt_agent(
    agent: Any,
    client_factory: Optional["A2AClientFactory"] = None,
    *,
    endpoint_url: Optional[str] = None,
) -> A2AAgentAdapter:
    """Convenience function to create an A2A adapter for an agent.

    Args:
        agent: The Agent to adapt
        client_factory: Optional A2AClientFactory
        endpoint_url: Optional HTTP endpoint URL

    Returns:
        A2AAgentAdapter instance
    """
    return A2AAgentAdapter(
        agent=agent,
        client_factory=client_factory,
        endpoint_url=endpoint_url,
    )

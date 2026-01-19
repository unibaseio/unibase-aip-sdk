"""A2A Agent Adapter - Adapts existing Agents to A2A protocol."""

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Optional
import json
import logging
import uuid

from a2a.types import (
    Task as A2ATask,
    TaskState,
    TaskStatus,
    Message,
    TaskStatusUpdateEvent,
    Artifact,
    TextPart,
    AgentCard,
    AgentSkill,
    AgentProvider,
    Role,
)
from a2a.utils.message import get_message_text

from aip_sdk.types import Task as SDKTask, TaskResult, AgentContext, AgentMessage, MessageContext
from aip_sdk.messaging import MessageHelpers, AIPMetadata

if TYPE_CHECKING:
    from aip_sdk.gateway.a2a_client import GatewayA2AClient
    from unibase_agent_sdk.a2a import StreamResponse

logger = logging.getLogger(__name__)


def parse_agent_message(message: Message) -> AgentMessage:
    """Parse an A2A Message into AgentMessage format.

    Uses MessageHelpers for simplified parsing.
    """
    # First try to parse as JSON with old format
    text = get_message_text(message)

    try:
        data = json.loads(text)
        if "intent" in data and "context" in data:
            return AgentMessage.from_dict(data)
    except json.JSONDecodeError:
        pass

    # Convert A2A Message to AgentMessage format
    aip_meta = MessageHelpers.get_aip_metadata(message)
    structured = MessageHelpers.get_structured_data(message)

    agent_msg_dict = {
        "intent": text,
        "context": {
            "run_id": aip_meta.run_id if aip_meta else "",
            "caller_id": aip_meta.caller_id if aip_meta else "",
            "caller_chain": aip_meta.caller_chain if aip_meta else [],
            "conversation_id": aip_meta.conversation_id if aip_meta else None,
            "payment_authorized": aip_meta.payment_authorized if aip_meta else True,
            "metadata": aip_meta.custom if aip_meta else {},
        }
    }

    if aip_meta and aip_meta.routing_hints:
        agent_msg_dict["hints"] = aip_meta.routing_hints.to_dict()

    if structured:
        agent_msg_dict["structured_data"] = structured

    return AgentMessage.from_dict(agent_msg_dict)


def task_result_to_message(result: TaskResult) -> Message:
    """Convert a TaskResult to an A2A Message.

    Uses MessageHelpers for consistent message format.
    """
    # Build response text
    if result.success:
        text = result.summary or json.dumps(result.output, indent=2)
    else:
        text = f"Error: {result.error or 'Unknown error'}"

    # Use MessageHelpers to create properly formatted agent message
    return MessageHelpers.create_agent_message(
        text=text,
        success=result.success,
        output=result.output if result.success else None,
        error=result.error if not result.success else None,
    )


def agent_config_to_card(
    agent_id: str,
    config: Any,
    endpoint_url: Optional[str] = None,
) -> AgentCard:
    """Convert an AgentConfig to an A2A AgentCard."""
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
    """Adapts an existing Agent to A2A protocol."""

    def __init__(
        self,
        agent: Any,
        gateway_client: Optional["GatewayA2AClient"] = None,
        *,
        endpoint_url: Optional[str] = None,
    ):
        """Initialize the adapter.

        Args:
            agent: The agent to adapt.
            gateway_client: The GatewayA2AClient for invoking other agents.
            endpoint_url: The endpoint URL of this agent.
        """
        self._agent = agent
        self._gateway_client = gateway_client
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
        """Create an AgentContext for the task."""
        gateway_client = self._gateway_client

        async def invoke_agent(
            agent_id: str,
            sub_task: Any,
            reason: str = "",
        ) -> TaskResult:
            """Invoke another agent via A2A through gateway.

            Uses MessageHelpers for message creation and parsing.
            """
            if not gateway_client:
                return TaskResult.error_result(
                    "Agent invocation not available (no gateway client)"
                )

            # Convert task to A2A message using MessageHelpers
            if isinstance(sub_task, dict):
                payload = sub_task
            elif hasattr(sub_task, "payload"):
                payload = sub_task.payload
            else:
                payload = {"intent": str(sub_task)}

            # Create proper A2A message with AIP metadata
            text = payload.get("intent", str(payload)) if isinstance(payload, dict) else str(payload)
            message = MessageHelpers.create_user_message(
                text=text,
                run_id=str(uuid.uuid4()),
                caller_id=task.context_id or "unknown",
                structured_data=payload if isinstance(payload, dict) else None,
            )

            try:
                result_task = await gateway_client.send_task(
                    agent_id=agent_id,
                    message=message,
                    context_id=task.context_id,
                )

                # Convert A2A Task to TaskResult
                if result_task.status.state == TaskState.completed:
                    # Get response from history
                    output = {}
                    summary = ""

                    if result_task.history:
                        last_msg = result_task.history[-1]
                        if last_msg.role == Role.agent:
                            summary = MessageHelpers.get_text(last_msg)
                            output = MessageHelpers.get_structured_data(last_msg) or {}

                    # Add artifacts if present
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
                        error_msg = MessageHelpers.get_text(result_task.status.message)
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
    ) -> AsyncGenerator["StreamResponse", None]:
        """Handle an A2A Task by calling the wrapped agent."""
        from unibase_agent_sdk.a2a import StreamResponse

        run_id = task.context_id or str(uuid.uuid4())

        # Emit initial working status
        yield StreamResponse(
            status_update=TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.working),
            )
        )

        try:
            # Get the last user message from history
            user_message = None
            for msg in reversed(task.history):
                if msg.role == Role.user:
                    user_message = msg
                    break

            if not user_message:
                # No user message, create error response
                yield StreamResponse(
                    status_update=TaskStatusUpdateEvent(
                        task_id=task.id,
                        context_id=task.context_id,
                        status=TaskStatus(
                            state=TaskState.failed,
                            message=Message.agent("No user message in task"),
                        ),
                        final=True,
                    )
                )
                return

            # Parse message using new AgentMessage format
            agent_message = parse_agent_message(user_message)

            # Log the parsed message for debugging
            logger.debug(
                "Parsed agent message",
                extra={
                    "intent": agent_message.intent[:100] if agent_message.intent else None,
                    "run_id": agent_message.context.run_id,
                    "caller_id": agent_message.context.caller_id,
                    "has_hints": agent_message.hints is not None,
                }
            )

            # Extract payload
            payload: Dict[str, Any] = {
                "intent": agent_message.intent,
                "context": agent_message.context.to_dict(),
            }
            if agent_message.hints:
                payload["hints"] = agent_message.hints.to_dict()
            if agent_message.structured_data:
                payload["structured_data"] = agent_message.structured_data

            # Create SDK Task
            sdk_task = SDKTask(
                task_id=task.id,
                name=payload.get("task_name", "execute"),
                description=agent_message.intent,
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
            final_state = TaskState.completed if result.success else TaskState.failed
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
                        state=TaskState.failed,
                        message=Message.agent(str(e)),
                    ),
                    final=True,
                )
            )


def adapt_agent(
    agent: Any,
    gateway_client: Optional["GatewayA2AClient"] = None,
    *,
    endpoint_url: Optional[str] = None,
) -> A2AAgentAdapter:
    """Convenience function to create an A2A adapter for an agent.

    Args:
        agent: The agent to adapt.
        gateway_client: The GatewayA2AClient for invoking other agents.
        endpoint_url: The endpoint URL of this agent.

    Returns:
        An A2AAgentAdapter wrapping the agent.
    """
    return A2AAgentAdapter(
        agent=agent,
        gateway_client=gateway_client,
        endpoint_url=endpoint_url,
    )

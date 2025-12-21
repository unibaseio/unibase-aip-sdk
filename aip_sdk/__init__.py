"""
Unibase AIP SDK

A simple, developer-friendly SDK for building and deploying AI agents
on the Unibase Agent Interoperability Protocol.

Quick Start:
    # Create an agent with a decorator
    from aip_sdk import Agent, skill

    @Agent(name="My Agent", description="A helpful agent", price=0.001)
    async def my_agent_handler(task, context):
        return {"result": "Hello from my agent!"}

    # Run as a service
    from aip_sdk import serve_agent
    serve_agent(my_agent_handler, port=8100)

Client Usage:
    from aip_sdk import AIPClient

    # Connect to AIP platform
    async with AIPClient("http://localhost:8001") as client:
        # List agents
        agents = await client.list_agents()

        # Run a task
        result = await client.run("What is the weather?")
        print(result.output)

Class-Based Agent:
    from aip_sdk import Agent, skill
    
    @Agent(name="Calculator", description="Math operations")
    class Calculator:
        @skill("calculate", "Perform calculations")
        async def calculate(self, task, context):
            expr = task.get("expression", "0")
            return {"result": eval(expr)}
"""

from aip_sdk.client import (
    AIPClient,
    AsyncAIPClient,
    create_client,
    async_client,
)
from aip_sdk.agent_builder import (
    AgentBuilder,
    Agent,
    skill,
    SkillBuilder,
    SDKAgent,
    create_agent,
)
from aip_sdk.types import (
    Task,
    TaskResult,
    AgentContext,
    AgentConfig,
    SkillConfig,
    CostModel,
    SkillInput,
    SkillOutput,
    RunResult,
    EventData,
    AgentInfo,
    TaskStatus,
    PaginatedResponse,
    UserInfo,
    PriceInfo,
)
from aip_sdk.exceptions import (
    AIPError,
    ConnectionError,
    AuthenticationError,
    RegistrationError,
    ExecutionError,
    PaymentError,
    ValidationError,
    TimeoutError,
    AgentNotFoundError,
)
from aip_sdk.service import (
    serve_agent,
    serve_agent_async,
    create_agent_app,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Client
    "AIPClient",
    "AsyncAIPClient",
    "create_client",
    "async_client",
    # Agent Building
    "AgentBuilder",
    "Agent",
    "skill",
    "SkillBuilder",
    "SDKAgent",
    "create_agent",
    # Types
    "Task",
    "TaskResult",
    "AgentContext",
    "AgentConfig",
    "SkillConfig",
    "CostModel",
    "SkillInput",
    "SkillOutput",
    "RunResult",
    "EventData",
    "AgentInfo",
    "TaskStatus",
    "PaginatedResponse",
    "UserInfo",
    "PriceInfo",
    # Exceptions
    "AIPError",
    "ConnectionError",
    "AuthenticationError",
    "RegistrationError",
    "ExecutionError",
    "PaymentError",
    "ValidationError",
    "TimeoutError",
    "AgentNotFoundError",
    # Service
    "serve_agent",
    "serve_agent_async",
    "create_agent_app",
]

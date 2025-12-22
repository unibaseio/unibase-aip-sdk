"""
Agent Service Module

Provides utilities for running SDK agents as HTTP services.

Example:
    from aip_sdk import Agent
    from aip_sdk.service import serve_agent

    @Agent(name="Weather", description="Weather service")
    async def weather_handler(task, context):
        return {"weather": "sunny"}

    # Run as a service
    serve_agent(weather_handler, port=8100)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from aip_sdk.agent_builder import SDKAgent
from aip_sdk.types import AgentConfig

logger = logging.getLogger(__name__)


def create_agent_app(
    agent: Union[SDKAgent, AgentConfig],
    *,
    host: str = "0.0.0.0",
    port: int = 8100,
    title: Optional[str] = None,
) -> Any:
    """
    Create a FastAPI app for serving an agent.
    
    Args:
        agent: The agent to serve
        host: Host to bind to
        port: Port to listen on
        title: Optional API title
        
    Returns:
        FastAPI application
    """
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
        from pydantic import BaseModel, Field
    except ImportError:
        raise ImportError(
            "FastAPI is required for serving agents. "
            "Install with: pip install fastapi uvicorn"
        )
    
    # Get agent config
    if isinstance(agent, SDKAgent):
        config = agent.config
        sdk_agent = agent
    else:
        config = agent
        sdk_agent = None
    
    app_title = title or f"{config.name} Service"
    
    # Create app with lifespan
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(f"Starting {config.name} service on port {port}")
        yield
        logger.info(f"Shutting down {config.name} service")
    
    app = FastAPI(
        title=app_title,
        description=config.description,
        lifespan=lifespan,
    )
    
    # Request/Response models
    class TaskPayload(BaseModel):
        task_id: str = Field(default_factory=lambda: str(uuid4()))
        name: str = ""
        description: str = ""
        payload: Dict[str, Any] = Field(default_factory=dict)
    
    class TaskResponse(BaseModel):
        output: Dict[str, Any]
        summary: str
        success: bool = True
        error: Optional[str] = None
    
    # Health endpoint
    @app.get("/healthz")
    async def health_check():
        return {"status": "healthy", "agent": config.name}
    
    # Agent card endpoint
    @app.get("/card")
    async def get_card():
        """Get the agent card."""
        handle = config.handle or config.name.lower().replace(" ", "_")
        endpoint_url = config.endpoint_url or f"http://localhost:{port}"
        
        return {
            "agent_id": f"erc8004:{handle}",
            "handle": handle,
            "name": config.name,
            "description": config.description,
            "capabilities": config.capabilities,
            "skills": [s.to_dict() for s in config.skills],
            "endpoint_url": endpoint_url,
            "cost_model": config.cost_model.to_dict(),
            "metadata": {
                "service_port": port,
                **config.metadata,
            },
        }
    
    # Invoke endpoint
    @app.post("/invoke", response_model=TaskResponse)
    async def invoke_task(task: TaskPayload):
        """Invoke the agent with a task."""
        if sdk_agent is None:
            raise HTTPException(
                status_code=500,
                detail="Agent handler not configured",
            )
        
        try:
            # Create domain task
            from aip_sdk._internal import TaskSpec, AgentExecutionContext

            domain_task = TaskSpec(
                task_id=task.task_id,
                name=task.name or config.skills[0].name if config.skills else "default",
                description=task.description,
                payload=task.payload,
            )

            # Create minimal context
            context = AgentExecutionContext(
                invoke_agent=_noop_invoke,
                emit_event=lambda e: logger.debug(f"Event: {e}"),
                send_message=_noop_send,
                receive_message=_noop_receive,
                memory_read=lambda s: {},
                memory_write=lambda s, d, desc: None,
            )
            
            # Execute task
            result = await sdk_agent.perform_task(domain_task, context)
            
            return TaskResponse(
                output=result.output,
                summary=result.summary,
                success=True,
            )
            
        except Exception as e:
            logger.exception(f"Error invoking agent: {e}")
            return TaskResponse(
                output={"error": str(e)},
                summary=str(e),
                success=False,
                error=str(e),
            )

    # NOTE: A2A protocol endpoints have been removed from this module.
    # Use unibase_agent_sdk.a2a.A2AServer for full A2A protocol support.
    # This simple server only provides basic /execute endpoint.

    return app


async def _noop_invoke(agent_id, task, reason):
    """No-op invoke for standalone service."""
    from aip_sdk._internal import AgentInvocationResult
    return AgentInvocationResult(
        output={"error": "Agent invocation not available in standalone mode"},
        summary="Agent invocation not available",
    )


async def _noop_send(message):
    """No-op message send."""
    pass


async def _noop_receive(conversation_id, timeout):
    """No-op message receive."""
    return None


def serve_agent(
    agent: Union[SDKAgent, AgentConfig],
    *,
    host: str = "0.0.0.0",
    port: int = 8100,
    reload: bool = False,
    log_level: str = "info",
    enable_a2a: bool = False,
) -> None:
    """
    Run an agent as an HTTP service.

    Args:
        agent: The agent to serve
        host: Host to bind to
        port: Port to listen on
        reload: Enable auto-reload for development
        log_level: Logging level
        enable_a2a: If True, use unibase-agent-sdk A2A server for full A2A protocol support.
                    If False (default), use simple FastAPI server with basic /execute endpoint.

    Note:
        For full A2A protocol support (streaming, task lifecycle, JSON-RPC 2.0),
        set enable_a2a=True and ensure unibase-agent-sdk is installed:
            pip install unibase-agent-sdk
    """
    if enable_a2a:
        # Use agent-sdk's full A2A server implementation
        try:
            from unibase_agent_sdk.a2a import A2AServer, AgentCard, Skill
            import asyncio
        except ImportError:
            raise ImportError(
                "unibase-agent-sdk is required for A2A protocol support. "
                "Install with: pip install unibase-agent-sdk\n"
                "Or use enable_a2a=False for basic serving without A2A."
            )

        # Convert SDKAgent/AgentConfig to AgentCard
        config = agent.config if isinstance(agent, SDKAgent) else agent
        agent_card = AgentCard(
            name=config.name,
            description=config.description,
            url=f"http://{host}:{port}",
            version="1.0.0",
            skills=[
                Skill(
                    id=skill.name,
                    name=skill.name,
                    description=skill.description,
                    tags=[],
                    examples=[]
                )
                for skill in config.skills
            ]
        )

        # Create task handler wrapper
        async def task_handler(task, message):
            """Wrap agent execution for A2A protocol."""
            from unibase_agent_sdk.a2a import StreamResponse, Message as A2AMessage
            from aip_sdk._internal import TaskSpec, AgentExecutionContext

            # Extract text from message
            text_content = ""
            for part in message.parts:
                if hasattr(part, 'text'):
                    text_content += part.text

            # Create task for agent
            domain_task = TaskSpec(
                task_id=task.id,
                name="a2a.request",
                description=text_content,
                payload={"message": text_content},
            )

            # Execute agent
            sdk_agent = agent if isinstance(agent, SDKAgent) else None
            if sdk_agent:
                context = AgentExecutionContext(
                    invoke_agent=_noop_invoke,
                    emit_event=lambda e: None,
                    send_message=_noop_send,
                    receive_message=_noop_receive,
                    memory_read=lambda s: {},
                    memory_write=lambda s, d, desc: None,
                )
                result = await sdk_agent.perform_task(domain_task, context)
                yield StreamResponse(message=A2AMessage.agent(result.summary))
            else:
                yield StreamResponse(message=A2AMessage.agent("Agent execution not configured"))

        # Run A2A server
        server = A2AServer(
            agent_card=agent_card,
            task_handler=task_handler,
            host=host,
            port=port
        )

        print(f"🚀 Starting A2A Server for {config.name} on {host}:{port}")
        print(f"   Agent Card: http://{host}:{port}/.well-known/agent.json")
        print(f"   A2A Endpoint: http://{host}:{port}/a2a")
        asyncio.run(server.run())

    else:
        # Use simple FastAPI server (original implementation)
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "Uvicorn is required for serving agents. "
                "Install with: pip install uvicorn"
            )

        app = create_agent_app(agent, host=host, port=port)

        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
        )


async def serve_agent_async(
    agent: Union[SDKAgent, AgentConfig],
    *,
    host: str = "0.0.0.0",
    port: int = 8100,
    log_level: str = "info",
) -> None:
    """
    Run an agent as an HTTP service (async version).
    
    Args:
        agent: The agent to serve
        host: Host to bind to
        port: Port to listen on
        log_level: Logging level
    """
    try:
        import uvicorn
    except ImportError:
        raise ImportError(
            "Uvicorn is required for serving agents. "
            "Install with: pip install uvicorn"
        )
    
    app = create_agent_app(agent, host=host, port=port)
    
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=log_level,
    )
    server = uvicorn.Server(config)
    await server.serve()

"""A2A Protocol Server."""

from ag_ui.core import UserMessage
from typing import Optional, Callable, AsyncIterator, Dict, Any
from contextlib import asynccontextmanager
import json
import asyncio
import uuid
from datetime import datetime

from ..core.exceptions import TaskExecutionError, InitializationError
from ..utils.logger import get_logger
from ..utils.config import get_default_aip_endpoint

logger = get_logger("a2a.server")

# Import directly from Google A2A SDK
from a2a.types import (
    AgentCard,
    Task,
    TaskState,
    TaskStatus,
    Message,
    TextPart,
    Role,
)
from a2a.utils.message import get_message_text
from a2a.client.helpers import create_text_message_object

# Import Unibase extensions
from .types import StreamResponse, A2AErrorCode


class A2AServer:
    """A2A-compliant server for exposing Unibase agents."""

    def __init__(
        self,
        agent_card: AgentCard,
        task_handler: Callable[[Task, Message], AsyncIterator[StreamResponse]],
        host: str = "0.0.0.0",
        port: int = 8000,
        registration_config: Optional[Dict[str, Any]] = None,
        auto_register: bool = True,
    ):
        """Initialize A2A server."""
        self.agent_card = agent_card
        self.task_handler = task_handler
        self.host = host
        self.port = port
        self.registration_config = registration_config
        self.auto_register = auto_register

        # Task storage (in-memory for now)
        self._tasks: Dict[str, Task] = {}

        # Registration state
        self._agent_id: Optional[str] = None
        self._aip_client = None

        # Gateway polling state
        self._polling_task: Optional[asyncio.Task] = None
        self._should_poll = False

        # Create FastAPI app
        self._app = None

    def _serialize_agent_card(self) -> Dict[str, Any]:
        """Serialize agent card to dict using Pydantic."""
        card_data = self.agent_card.model_dump(by_alias=True, exclude_none=True)

        # Add endpoint_url if available in registration_config
        endpoint_url = None
        if self.registration_config:
            endpoint_url = self.registration_config.get("endpoint_url")
            if endpoint_url:
                card_data["endpoint_url"] = endpoint_url
                card_data["url"] = endpoint_url

        # Ensure url is set (fallback to host:port if missing and not in push mode)
        if "url" not in card_data:
            card_data["url"] = f"http://{self.host}:{self.port}"

        return card_data

    def _serialize_task(self, task: Task) -> Dict[str, Any]:
        """Serialize task to dict using Pydantic."""
        return task.model_dump(by_alias=True, exclude_none=True)

    def _parse_message(self, message_data: Dict[str, Any]) -> Message:
        """Parse message from dict using Pydantic."""
        return Message.model_validate(message_data)

    def create_app(self):
        """Create and configure the FastAPI application."""
        try:
            from fastapi import FastAPI, Request, Response
            from fastapi.responses import JSONResponse, StreamingResponse
            from fastapi.middleware.cors import CORSMiddleware
        except ImportError:
            raise InitializationError(
                "FastAPI is required for A2A server. "
                "Install it with: pip install fastapi uvicorn"
            )

        @asynccontextmanager
        async def lifespan(app):
            logger.info(f"A2A Server starting at http://{self.host}:{self.port}")
            logger.info(f"Agent Card: http://{self.host}:{self.port}/.well-known/agent-card.json")

            # Register with AIP platform if configured and auto_register is True
            if self.registration_config and self.auto_register:
                await self._register_with_aip()

            # Start Gateway polling if endpoint_url is None (private mode)
            if self.registration_config:
                endpoint_url = self.registration_config.get("endpoint_url")
                gateway_url = self.registration_config.get("gateway_url")

                if endpoint_url is None and gateway_url:
                    logger.info(f"Starting Gateway polling mode (private agent)")
                    logger.info(f"  Gateway URL: {gateway_url}")
                    logger.info(f"  Agent Handle: {self.registration_config.get('handle')}")
                    self._should_poll = True
                    self._polling_task = asyncio.create_task(self._gateway_polling_loop())

            yield

            # Cleanup on shutdown
            self._should_poll = False
            if self._polling_task:
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass
            if self._aip_client:
                await self._aip_client.close()
            logger.info("A2A Server shutting down")

        app = FastAPI(
            title=self.agent_card.name,
            description=self.agent_card.description,
            version=self.agent_card.version,
            lifespan=lifespan
        )

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Agent Card endpoint
        @app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            return JSONResponse(content=self._serialize_agent_card())

        # JSON-RPC endpoint - available at both / and /a2a for compatibility
        # Google A2A protocol expects JSONRPC at root URL
        @app.post("/")
        @app.post("/a2a")
        async def jsonrpc_endpoint(request: Request):
            try:
                body = await request.json()
                rpc_request = self._parse_jsonrpc_request(body)

                # Route to appropriate handler
                result = await self._handle_jsonrpc(rpc_request, body.get("id"))

                return JSONResponse(content=result)

            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": A2AErrorCode.PARSE_ERROR, "message": "Invalid JSON"}
                }
                return JSONResponse(content=error_response, status_code=400)
            except Exception as e:
                logger.exception(f"Error handling JSON-RPC request: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": A2AErrorCode.INTERNAL_ERROR, "message": str(e)}
                }
                return JSONResponse(content=error_response, status_code=500)

        # Streaming endpoint using SSE
        @app.post("/a2a/stream")
        async def stream_endpoint(request: Request):
            try:
                body = await request.json()
                rpc_request = self._parse_jsonrpc_request(body)

                if rpc_request["method"] != "message/stream":
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "error": {"code": A2AErrorCode.METHOD_NOT_FOUND, "message": "Streaming only supports message/stream"}
                    }
                    return JSONResponse(content=error_response, status_code=400)

                async def event_generator():
                    async for response in self._handle_message_stream(rpc_request, body.get("id")):
                        data = json.dumps(response)
                        yield f"data: {data}\n\n"

                return StreamingResponse(
                    event_generator(),
                    media_type="text/event-stream"
                )

            except Exception as e:
                logger.exception(f"Error in stream endpoint: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": A2AErrorCode.INTERNAL_ERROR, "message": str(e)}
                }
                return JSONResponse(content=error_response, status_code=500)

        # AG-UI Streaming endpoint (Raw SSE support)
        @app.post("/agui/stream")
        async def stream_agui_endpoint(request: Request):
            try:
                body = await request.json()
                user_msg = UserMessage.model_validate(body)
                # Manually convert ag_ui UserMessage to SDK Message
                # ag_ui UserMessage: id, role, content (list or str), name, etc.
                # SDK Message: messageId, role, parts, metadata, etc.
                
                # Check for content type
                parts = []
                if isinstance(user_msg.content, str):
                    parts.append({"text": user_msg.content})
                elif isinstance(user_msg.content, list):
                     for item in user_msg.content:
                         # item is ContentItem (TextInputContent, BinaryInputContent, etc.)
                         # dumping to dict to get properties
                         item_dict = item.model_dump(by_alias=True)
                         # Simple mapping for now - adjust based on actual SDK Message structure
                         if "text" in item_dict:
                             parts.append({"text": item_dict["text"]})
                         # TODO: Handle binary content if SDK Message supports it
                
                conversation_id = body.get("id")

                msg_data = {
                    "messageId": uuid.uuid4().hex,
                    "role": user_msg.role,
                    "parts": parts,
                    "metadata": {} # Add metadata if available
                }
                
                msg = self._parse_message(msg_data)
                
                async def event_generator():
                    # Determine task (conversation) context
                    task_id = conversation_id or uuid.uuid4().hex
                    
                    if task_id in self._tasks:
                        # Continue existing conversation
                        existing_task = self._tasks[task_id]
                        task = Task(
                            id=existing_task.id,
                            context_id=existing_task.context_id,
                            status=TaskStatus(state=TaskState.working),
                            history=list(existing_task.history or []) + [msg],
                            artifacts=existing_task.artifacts,
                            metadata=existing_task.metadata,
                        )
                        # Build history for context (append new message)
                    else:
                        # New conversation
                        task = Task(
                            id=task_id,
                            context_id=uuid.uuid4().hex,
                            status=TaskStatus(state=TaskState.working),
                            history=[msg],
                        )

                    # Update/Save task
                    self._tasks[task.id] = task

                    history = list(task.history or [])
                    artifacts = list(task.artifacts or [])

                    accumulated_content = []
                    initial_history_len = len(history)

                    async for response in self.task_handler(task, msg):
                        if response.message:
                             history.append(response.message)
                        if response.status_update:
                             task = Task(
                                 id=task.id,
                                 context_id=task.context_id,
                                 status=response.status_update.status,
                                 history=history,
                                 artifacts=artifacts if artifacts else None,
                                 metadata=task.metadata,
                             )
                        if response.artifact_update:
                             artifacts.append(response.artifact_update.artifact)
                        
                        # Update task in storage
                        self._tasks[task.id] = task

                        if response.raw_content:
                             # Try to extract text content from raw SSE for history (best effort)
                             try:
                                 # Common format: data: "text"\n\n or data: "text"
                                 line = response.raw_content.strip()
                                 if line.startswith("data:"):
                                     content = line[5:].strip()
                                     # Handle JSON string if present
                                     try:
                                         if content.startswith('"') and content.endswith('"'):
                                             content = json.loads(content)
                                         elif content.startswith("{") and content.endswith("}"):
                                             # Try to parse JSON object (e.g. OpenAI format or custom A2A format)
                                             try:
                                                 json_data = json.loads(content)
                                                 if isinstance(json_data, dict):
                                                     # Extract content from common formats
                                                     if "delta" in json_data:
                                                         content = json_data["delta"]
                                                     elif "text" in json_data:
                                                         content = json_data["text"]
                                                     elif "choices" in json_data and isinstance(json_data["choices"], list):
                                                         # OpenAI format
                                                         delta = json_data["choices"][0].get("delta", {})
                                                         if "content" in delta:
                                                             content = delta["content"]
                                             except:
                                                  pass
                                     except:
                                         pass
                                     if isinstance(content, str):
                                         accumulated_content.append(content)
                                 elif line.startswith("0:"):
                                      # Vercel AI SDK format: 0:"text"\n
                                      content = line[2:].strip()
                                      if content.startswith('"') and content.endswith('"'):
                                            try:
                                                content = json.loads(content)
                                                accumulated_content.append(content)
                                            except:
                                                pass
                             except Exception:
                                 pass

                             yield response.raw_content
                        else:
                             # If not raw content, try to get event
                             event = response.get_event()
                             if event:
                                 # For simplicity, just json dump if it happens to be not raw
                                 # But for ag_ui stream, we expect raw content mostly
                                 yield f"data: {json.dumps(event.model_dump(by_alias=True))}\n\n"
                    
                    # If we accumulated content but no message was added to history, synthesize one
                    if accumulated_content and len(history) == initial_history_len:
                        full_text = "".join(accumulated_content)
                        if full_text:
                            # Create agent message using imported helper
                            agent_msg = create_text_message_object(Role.agent, full_text)
                            history.append(agent_msg)
                    
                    # Finalize task state
                    final_state = task.status.state
                    if final_state not in [TaskState.completed, TaskState.failed, TaskState.canceled]:
                        final_state = TaskState.completed
                    
                    task = Task(
                        id=task.id,
                        context_id=task.context_id,
                        status=TaskStatus(state=final_state),
                        history=history,
                        artifacts=artifacts if artifacts else None,
                        metadata=task.metadata,
                    )
                    self._tasks[task.id] = task
                    
                return StreamingResponse(
                    event_generator(),
                    media_type="text/event-stream"
                )

            except Exception as e:
                logger.exception(f"Error in stream-agui endpoint: {e}")
                error_response = {
                    "code": A2AErrorCode.INTERNAL_ERROR, 
                    "message": str(e)
                }
                return JSONResponse(content=error_response, status_code=500)

        # Health check
        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "agent": self.agent_card.name}

        # Health check (alternative endpoint for gateway compatibility)
        @app.get("/healthz")
        async def healthz_check():
            return {"status": "healthy", "agent": self.agent_card.name}

        # Chat history endpoint
        @app.get("/conversations")
        async def get_conversations(
            limit: int = 20,
            offset: int = 0
        ):
            """Get recent chat history."""
            # Filter tasks that have last_updated in metadata
            tasks_with_time = []
            for task in self._tasks.values():
                if task.metadata and "last_updated" in task.metadata:
                    tasks_with_time.append(task)
            
            # Sort by last_updated descending
            try:
                tasks_with_time.sort(
                    key=lambda t: t.metadata["last_updated"],
                    reverse=True
                )
            except Exception:
                # Fallback if sorting fails (should't happen if properly formatted)
                pass
                
            # Paginate
            paginated_tasks = tasks_with_time[offset : offset + limit]
            
            return {
                "data": [self._serialize_task(t) for t in paginated_tasks],
                "total": len(tasks_with_time),
                "limit": limit,
                "offset": offset
            }

        @app.get("/conversations/{conversation_id}")
        async def get_conversation(conversation_id: str):
            """Get specific conversation details."""
            if conversation_id not in self._tasks:
                return JSONResponse(status_code=404, content={"error": "Conversation not found"})
            
            return self._serialize_task(self._tasks[conversation_id])

        self._app = app
        return app

    def _parse_jsonrpc_request(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and validate JSON-RPC request."""
        if body.get("jsonrpc") != "2.0":
            raise ValueError("Invalid JSON-RPC version")
        if "method" not in body:
            raise ValueError("Missing method")
        return {
            "method": body["method"],
            "params": body.get("params", {}),
            "id": body.get("id"),
        }

    async def _handle_jsonrpc(self, request: Dict[str, Any], request_id: Any) -> Dict[str, Any]:
        """Handle JSON-RPC request and return response."""
        method_handlers = {
            "message/send": self._handle_message_send,
            "tasks/get": self._handle_tasks_get,
            "tasks/list": self._handle_tasks_list,
            "tasks/cancel": self._handle_tasks_cancel,
        }

        handler = method_handlers.get(request["method"])
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": A2AErrorCode.METHOD_NOT_FOUND, "message": f"Method not found: {request['method']}"}
            }

        try:
            result = await handler(request["params"])
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
        except TaskExecutionError as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": A2AErrorCode.TASK_NOT_FOUND, "message": str(e)}
            }
        except Exception as e:
            logger.exception(f"Error handling {request['method']}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": A2AErrorCode.INTERNAL_ERROR, "message": str(e)}
            }

    async def _handle_message_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle message/send method."""
        # Parse message from params
        message_data = params.get("message", {})
        message = self._parse_message(message_data)

        # Get or create task
        task_id = params.get("id") or str(uuid.uuid4())
        context_id = params.get("contextId") or str(uuid.uuid4())

        if task_id in self._tasks:
            task = self._tasks[task_id]
            # Add message to history
            task = Task(
                id=task.id,
                context_id=task.context_id,
                status=task.status,
                history=list(task.history or []) + [message],
                artifacts=task.artifacts,
                metadata=task.metadata,
            )
        else:
            task = Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.submitted),
                history=[message],
            )

        self._tasks[task_id] = task

        # Update task status to working
        # Add last_updated to metadata
        task_metadata = task.metadata or {}
        task_metadata["last_updated"] = datetime.utcnow().isoformat()

        task = Task(
            id=task.id,
            context_id=task.context_id,
            status=TaskStatus(state=TaskState.working),
            history=task.history,
            artifacts=task.artifacts,
            metadata=task_metadata,
        )
        self._tasks[task_id] = task

        # Process the message (collect all stream responses)
        try:
            history = list(task.history or [])
            artifacts = list(task.artifacts or [])

            async for response in self.task_handler(task, message):
                if response.message:
                    history.append(response.message)
                if response.status_update:
                    task = Task(
                        id=task.id,
                        context_id=task.context_id,
                        status=response.status_update.status,
                        history=history,
                        artifacts=artifacts,
                        metadata=task.metadata,
                    )
                if response.artifact_update:
                    artifacts.append(response.artifact_update.artifact)

            # Mark as completed if not already in terminal state
            final_state = task.status.state
            if final_state not in [TaskState.completed, TaskState.failed, TaskState.canceled]:
                final_state = TaskState.completed

            task = Task(
                id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=final_state),
                history=history,
                artifacts=artifacts if artifacts else None,
                metadata=task.metadata,
            )

        except Exception as e:
            logger.exception(f"Error in task handler: {e}")
            error_message = create_text_message_object(Role.agent, f"Error: {str(e)}")
            task = Task(
                id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.failed, message=error_message),
                history=list(task.history or []),
                artifacts=task.artifacts,
                metadata=task.metadata,
            )

        self._tasks[task_id] = task

        # Return Task object (standard A2A protocol)
        # Add AIP events to task metadata
        aip_events = await self._get_aip_events()
        if aip_events:
            task_metadata = task.metadata or {}
            task_metadata["aip_events"] = aip_events
            task = Task(
                id=task.id,
                context_id=task.context_id,
                status=task.status,
                history=task.history,
                artifacts=task.artifacts,
                metadata=task_metadata,
            )

        return self._serialize_task(task)

    async def _handle_message_stream(
        self,
        request: Dict[str, Any],
        request_id: Any
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle message/stream method with SSE responses."""
        params = request["params"]
        message_data = params.get("message", {})
        message = self._parse_message(message_data)

        # Get or create task
        task_id = params.get("id") or str(uuid.uuid4())
        context_id = params.get("contextId") or str(uuid.uuid4())

        if task_id in self._tasks:
            task = self._tasks[task_id]
            task = Task(
                id=task.id,
                context_id=task.context_id,
                status=task.status,
                history=list(task.history or []) + [message],
                artifacts=task.artifacts,
                metadata=task.metadata,
            )
        else:
            task = Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.submitted),
                history=[message],
            )

        self._tasks[task_id] = task

        # Update task status to working
        # Add last_updated to metadata
        task_metadata = task.metadata or {}
        task_metadata["last_updated"] = datetime.utcnow().isoformat()

        task = Task(
            id=task.id,
            context_id=task.context_id,
            status=TaskStatus(state=TaskState.working),
            history=task.history,
            artifacts=task.artifacts,
            metadata=task_metadata,
        )
        self._tasks[task_id] = task

        # Stream responses
        try:
            history = list(task.history or [])
            artifacts = list(task.artifacts or [])

            async for response in self.task_handler(task, message):
                event = response.get_event()
                if event:
                    yield {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": event.model_dump(by_alias=True, exclude_none=True)
                    }

                # Update task state
                if response.message:
                    history.append(response.message)
                if response.status_update:
                    task = Task(
                        id=task.id,
                        context_id=task.context_id,
                        status=response.status_update.status,
                        history=history,
                        artifacts=artifacts if artifacts else None,
                        metadata=task.metadata,
                    )
                if response.artifact_update:
                    artifacts.append(response.artifact_update.artifact)

            # Final response with completed task
            final_state = task.status.state
            if final_state not in [TaskState.completed, TaskState.failed, TaskState.canceled]:
                final_state = TaskState.completed

            task = Task(
                id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=final_state),
                history=history,
                artifacts=artifacts if artifacts else None,
                metadata=task.metadata,
            )
            self._tasks[task_id] = task

            yield {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self._serialize_task(task)
            }

        except Exception as e:
            logger.exception(f"Error in stream handler: {e}")
            error_message = create_text_message_object(Role.agent, f"Error: {str(e)}")
            task = Task(
                id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.failed, message=error_message),
                history=list(task.history or []),
                artifacts=task.artifacts,
                metadata=task.metadata,
            )
            self._tasks[task_id] = task

            yield {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self._serialize_task(task)
            }

    async def _handle_tasks_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tasks/get method."""
        task_id = params.get("id")
        if not task_id or task_id not in self._tasks:
            raise TaskExecutionError(f"Task not found: {task_id}")
        return self._serialize_task(self._tasks[task_id])

    async def _handle_tasks_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tasks/list method."""
        tasks = list(self._tasks.values())

        # Apply filters if provided
        context_id = params.get("contextId")
        if context_id:
            tasks = [t for t in tasks if t.context_id == context_id]

        return {
            "tasks": [self._serialize_task(t) for t in tasks]
        }

    async def _handle_tasks_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tasks/cancel method."""
        task_id = params.get("id")
        if not task_id or task_id not in self._tasks:
            raise TaskExecutionError(f"Task not found: {task_id}")

        task = self._tasks[task_id]

        # Can only cancel non-terminal tasks
        if task.status.state in [TaskState.completed, TaskState.failed, TaskState.canceled]:
            raise TaskExecutionError(f"Task {task_id} is already in terminal state")

        task = Task(
            id=task.id,
            context_id=task.context_id,
            status=TaskStatus(state=TaskState.canceled),
            history=task.history,
            artifacts=task.artifacts,
            metadata=task.metadata,
        )
        self._tasks[task_id] = task
        return self._serialize_task(task)

    async def _register_with_aip(self):
        """Register agent with AIP platform."""
        if not self.registration_config:
            return

        try:
            from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig
        except ImportError:
            logger.warning(
                "aip_sdk not available, skipping AIP registration. "
                "Install with: pip install unibase-aip-sdk"
            )
            return

        config = self.registration_config
        user_id = config["user_id"]
        aip_endpoint = config["aip_endpoint"]
        handle = config["handle"]

        logger.info(f"[DEBUG] Registration config endpoint_url: {config.get('endpoint_url')}")
        logger.info(f"Registering agent with AIP platform at {aip_endpoint}")
        logger.info(f"  User ID: {user_id}")
        logger.info(f"  Handle: erc8004:{handle}")

        try:
            # Create AIP client
            self._aip_client = AsyncAIPClient(base_url=aip_endpoint)

            # Build agent config
            skills = [
                SkillConfig(
                    skill_id=s["id"],
                    name=s["name"],
                    description=s.get("description", ""),
                )
                for s in config.get("skills", [])
            ]

            # Import CostModel to reconstruct from dict
            from aip_sdk.types import CostModel
            cost_model_data = config.get("cost_model", {})
            cost_model = CostModel.from_dict(cost_model_data) if cost_model_data else CostModel()

            # Two modes:
            # - endpoint_url=None: polling mode (private agent behind firewall)
            # - endpoint_url=<URL>: push mode (public agent)
            endpoint_url = config.get("endpoint_url")

            agent_config = AgentConfig(
                name=config["name"],
                handle=handle,
                description=config.get("description", ""),
                endpoint_url=endpoint_url,
                skills=skills,
                cost_model=cost_model,
                currency=config.get("currency", "USD"),
                metadata=config.get("metadata", {}),
            )

            # Register with platform
            result = await self._aip_client.register_agent(user_id, agent_config)
            self._agent_id = result.get("agent_id", f"erc8004:{handle}")

            logger.info(f"Agent registered successfully: {self._agent_id}")

        except Exception as e:
            logger.warning(f"AIP registration failed (agent will run without registration): {e}")
            # Don't fail startup - agent can still work without platform registration

    async def _gateway_polling_loop(self):
        """Poll Gateway for tasks (for private agents behind firewall)."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx is required for Gateway polling")
            return

        config = self.registration_config
        gateway_url = config.get("gateway_url")
        handle = config.get("handle")
        poll_interval = 3.0  # Poll every 3 seconds

        logger.info(f"Starting Gateway polling loop for agent {handle}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            while self._should_poll:
                try:
                    # Poll for tasks
                    response = await client.get(
                        f"{gateway_url}/gateway/tasks/poll",
                        params={"agent": handle, "timeout": 5.0}
                    )

                    if response.status_code == 200:
                        task_data = response.json()
                        task_id = task_data.get("task_id")

                        if task_id:
                            logger.info(f"Received task {task_id} from Gateway")

                            # Process the task
                            await self._process_gateway_task(task_id, task_data, gateway_url, client)
                        else:
                            # No task available
                            await asyncio.sleep(poll_interval)
                    else:
                        # Poll failed, wait and retry
                        logger.debug(f"Poll returned {response.status_code}, retrying...")
                        await asyncio.sleep(poll_interval)

                except Exception as e:
                    logger.error(f"Error in polling loop: {e}")
                    await asyncio.sleep(poll_interval)

        logger.info("Gateway polling loop stopped")

    async def _process_gateway_task(self, task_id: str, task_data: Dict, gateway_url: str, client):
        """Process a task received from Gateway."""
        try:
            # Extract payload
            payload = task_data.get("payload", {})

            # Payload should be a complete JSON-RPC request
            # Extract the params from it
            rpc_request = {
                "method": payload.get("method", "message/send"),
                "params": payload.get("params", {}),  # Extract params from payload
                "id": payload.get("id")
            }

            # Handle the request using existing handler
            result = await self._handle_jsonrpc(rpc_request, rpc_request["id"])

            # Submit result back to Gateway
            await client.post(
                f"{gateway_url}/gateway/tasks/complete",
                json={
                    "task_id": task_id,
                    "status": "completed",
                    "result": result
                }
            )

            logger.info(f"Task {task_id} completed and result submitted")

        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}")

            # Submit error result
            try:
                await client.post(
                    f"{gateway_url}/gateway/tasks/complete",
                    json={
                        "task_id": task_id,
                        "status": "failed",
                        "error": str(e)
                    }
                )
            except Exception as submit_error:
                logger.error(f"Failed to submit error result: {submit_error}")

    async def _get_aip_events(self) -> Optional[list]:
        """Get recent AIP events (payments, memory) for this agent.

        Returns events in a format suitable for the AG-UI protocol.
        These events are included in the A2A response metadata and
        can be displayed by the frontend.
        """
        if not self.registration_config or not self._aip_client:
            return None

        try:
            import httpx
            from datetime import datetime

            aip_endpoint = self.registration_config.get("aip_endpoint", get_default_aip_endpoint())
            agent_id = self._agent_id or f"erc8004:{self.registration_config.get('handle', '')}"

            # Query AIP for recent events for this agent
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{aip_endpoint}/agents/{agent_id}/events",
                    params={"limit": 10, "types": "payment_settled,memory_uploaded"}
                )

                if response.status_code == 200:
                    events = response.json()
                    if events:
                        # Transform events to AG-UI compatible format
                        result = []
                        for event in events:
                            event_type = event.get("type", "")
                            if event_type in ("payment_settled", "payment.settled"):
                                result.append({
                                    "type": "payment",
                                    "agent_id": event.get("destination") or agent_id,
                                    "amount": float(event.get("amount", 0)),
                                    "currency": event.get("currency", "USD"),
                                    "timestamp": event.get("ts", datetime.now().isoformat()),
                                    "transaction_url": event.get("tx_url"),
                                    "status": "settled"
                                })
                            elif "memory" in event_type:
                                result.append({
                                    "type": "memory",
                                    "scope": event.get("scope") or event.get("key", "unknown"),
                                    "operation": event.get("operation", "write"),
                                    "timestamp": event.get("ts", datetime.now().isoformat()),
                                    "membase_url": event.get("membase_url"),
                                    "data_size": event.get("size")
                                })
                        return result if result else None
        except Exception as e:
            logger.debug(f"Failed to get AIP events: {e}")

        return None

    @property
    def agent_id(self) -> Optional[str]:
        """Get the registered agent ID (if registered with AIP)."""
        return self._agent_id

    async def run(self):
        """Start the A2A server."""
        try:
            import uvicorn
        except ImportError:
            raise InitializationError(
                "uvicorn is required to run the A2A server. "
                "Install it with: pip install uvicorn"
            )

        app = self.create_app()
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    def run_sync(self):
        """Start the A2A server synchronously."""
        asyncio.run(self.run())


def create_simple_handler(
    response_func: Callable[[str], str]
) -> Callable[[Task, Message], AsyncIterator[StreamResponse]]:
    """Create a simple task handler from a text-to-text function."""
    async def handler(task: Task, message: Message) -> AsyncIterator[StreamResponse]:
        # Extract text from message using Google A2A utility
        input_text = get_message_text(message)

        # Generate response
        response_text = response_func(input_text)

        # Yield response message using Google A2A helper
        response_msg = create_text_message_object(Role.agent, response_text)
        yield StreamResponse(message=response_msg)

    return handler


def create_async_handler(
    response_func: Callable[[str], Any]
) -> Callable[[Task, Message], AsyncIterator[StreamResponse]]:
    """Create a task handler from an async text-to-text function."""
    async def handler(task: Task, message: Message) -> AsyncIterator[StreamResponse]:
        input_text = get_message_text(message)
        response_text = await response_func(input_text)
        response_msg = create_text_message_object(Role.agent, response_text)
        yield StreamResponse(message=response_msg)

    return handler

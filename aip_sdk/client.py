"""
AIP Client Module

Provides client classes for interacting with the AIP platform.

Example:
    from aip_sdk import AIPClient

    # Async usage
    async with AIPClient("http://localhost:8001") as client:
        # List agents
        agents = await client.list_agents()

        # Run a task
        async for event in client.run_stream("Plan a trip to Tokyo"):
            print(event)

        # Or get the final result
        result = await client.run("What's the weather in SF?")
        print(result.output)
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

import httpx

from aip_sdk.types import (
    AgentConfig,
    AgentInfo,
    EventData,
    RunResult,
    TaskStatus,
    PaginatedResponse,
    UserInfo,
    PriceInfo,
)
from aip_sdk.exceptions import (
    AIPError,
    ConnectionError,
    ExecutionError,
    RegistrationError,
)
from aip_sdk.agent_builder import SDKAgent

logger = logging.getLogger(__name__)


@dataclass
class ClientConfig:
    """Configuration for the AIP client."""
    base_url: str = "http://localhost:8001"
    timeout: float = 60.0
    stream_timeout: float = 300.0
    max_retries: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


class AsyncAIPClient:
    """
    Async client for interacting with the AIP platform.
    
    Example:
        async with AsyncAIPClient("http://localhost:8001") as client:
            result = await client.run("What's the weather?")
            print(result.output)
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        *,
        timeout: float = 60.0,
        stream_timeout: float = 300.0,
        headers: Optional[Dict[str, str]] = None,
        config: Optional[ClientConfig] = None,
    ):
        """
        Initialize the async AIP client.
        
        Args:
            base_url: Base URL of the AIP platform
            timeout: Default timeout for requests
            stream_timeout: Timeout for streaming requests
            headers: Additional headers to include in requests
            config: Full client configuration
        """
        if config:
            self.config = config
        else:
            self.config = ClientConfig(
                base_url=base_url,
                timeout=timeout,
                stream_timeout=stream_timeout,
                headers=headers or {},
            )
        
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                headers=self.config.headers,
            )
        return self._client
    
    async def __aenter__(self) -> "AsyncAIPClient":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def close(self) -> None:
        """Close the client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # =========================================================================
    # Health & Status
    # =========================================================================
    
    async def health_check(self) -> bool:
        """
        Check if the AIP platform is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get("/healthz")
            return response.status_code == 200
        except Exception:
            return False
    
    async def wait_for_ready(
        self,
        max_attempts: int = 30,
        interval: float = 1.0,
    ) -> bool:
        """
        Wait for the AIP platform to be ready.
        
        Args:
            max_attempts: Maximum number of attempts
            interval: Seconds between attempts
            
        Returns:
            True if ready, False if timeout
        """
        for _ in range(max_attempts):
            if await self.health_check():
                return True
            await asyncio.sleep(interval)
        return False
    
    # =========================================================================
    # Agent Operations
    # =========================================================================

    async def list_user_agents(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """
        List agents owned by a specific user with pagination.

        Args:
            user_id: The user's ID
            limit: Maximum number of agents to return (default: 100)
            offset: Number of agents to skip (default: 0)

        Returns:
            PaginatedResponse containing AgentInfo objects
        """
        try:
            response = await self.client.get(
                f"/users/{user_id}/agents",
                params={"limit": limit, "offset": offset},
            )
            response.raise_for_status()
            data = response.json()

            agents = [AgentInfo.from_dict(agent) for agent in data["agents"]]

            return PaginatedResponse(
                items=agents,
                total=data["total"],
                limit=data["limit"],
                offset=data["offset"],
            )
        except httpx.HTTPStatusError as e:
            raise ConnectionError(
                f"Failed to list agents for user {user_id}: {e}",
                url=f"{self.config.base_url}/users/{user_id}/agents"
            )

    async def get_agent(self, user_id: str, agent_id: str) -> Optional[AgentInfo]:
        """
        Get information about a specific agent owned by a user.

        Args:
            user_id: The user's ID
            agent_id: The agent's ID

        Returns:
            Agent information or None if not found
        """
        agents_response = await self.list_user_agents(user_id, limit=1000)
        for agent in agents_response.items:
            if agent.agent_id == agent_id:
                return agent
        return None

    async def register_agent(
        self,
        user_id: str,
        agent: Union[SDKAgent, AgentConfig, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Register an agent for a specific user.

        Args:
            user_id: The user ID who will own this agent
            agent: Agent to register (SDKAgent, AgentConfig, or dict)

        Returns:
            Registration result with agent_id, handle, etc.

        Example:
            >>> config = AgentConfig(
            ...     name="My Agent",
            ...     description="A helpful agent",
            ...     price=0.001
            ... )
            >>> result = await client.register_agent("user:0x123...", config)
            >>> print(result["agent_id"])
        """
        # Convert to registration dict
        if isinstance(agent, SDKAgent):
            reg_data = agent.config.to_registration_dict()
        elif isinstance(agent, AgentConfig):
            reg_data = agent.to_registration_dict()
        else:
            reg_data = agent

        try:
            response = await self.client.post(
                f"/users/{user_id}/agents/register",
                json=reg_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise RegistrationError(
                f"Failed to register agent for user {user_id}: {e}",
                handle=reg_data.get("handle"),
            )

    async def unregister_agent(
        self,
        user_id: str,
        agent_id: str,
    ) -> Dict[str, Any]:
        """
        Unregister an agent owned by a user.

        Args:
            user_id: The user ID who owns the agent
            agent_id: The agent ID to unregister

        Returns:
            Unregistration result

        Example:
            >>> result = await client.unregister_agent(
            ...     "user:0x123...",
            ...     "erc8004:my_agent"
            ... )
            >>> print(result["status"])  # "unregistered"
        """
        try:
            response = await self.client.delete(
                f"/users/{user_id}/agents/{agent_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise AIPError(
                f"Failed to unregister agent {agent_id}: {e}"
            )

    async def register(
        self,
        user_id: str,
        agent: Union[SDKAgent, AgentConfig],
    ) -> Dict[str, Any]:
        """
        Alias for register_agent.

        Args:
            user_id: The user ID who will own this agent
            agent: Agent to register

        Returns:
            Registration result
        """
        return await self.register_agent(user_id, agent)
    
    # =========================================================================
    # Task Execution
    # =========================================================================
    
    async def run(
        self,
        objective: str,
        *,
        domain_hint: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> RunResult:
        """
        Execute a task and return the final result.
        
        Args:
            objective: The task objective/description
            domain_hint: Optional hint for agent routing
            user_id: Optional user ID for payment
            timeout: Optional custom timeout
            
        Returns:
            RunResult with status and output
        """
        events: List[EventData] = []
        payments: List[Dict[str, Any]] = []
        result = None
        error = None
        run_id = None

        try:
            async for event in self.run_stream(
                objective,
                domain_hint=domain_hint,
                user_id=user_id,
                timeout=timeout,
            ):
                events.append(event)
                run_id = run_id or event.run_id

                # Extract payment events
                if "payment" in event.event_type.lower():
                    payment_data = {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                    }
                    # Add all payload data
                    payment_data.update(event.payload)
                    payments.append(payment_data)

                if event.is_completed:
                    result = event.payload
                elif event.is_error:
                    error = event.message or str(event.payload)
        except Exception as e:
            error = str(e)

        from aip_sdk.types import RunStatus
        status = RunStatus.FAILED if error else RunStatus.COMPLETED

        return RunResult(
            run_id=run_id or "",
            status=status,
            result=result,
            events=events,
            error=error,
            payments=payments,
        )
    
    async def run_stream(
        self,
        objective: str,
        *,
        domain_hint: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[EventData, None]:
        """
        Execute a task and stream events.
        
        Args:
            objective: The task objective/description
            domain_hint: Optional hint for agent routing
            user_id: Optional user ID for payment
            timeout: Optional custom timeout
            
        Yields:
            EventData for each streaming event
        """
        payload: Dict[str, Any] = {"objective": objective}
        if domain_hint:
            payload["domain_hint"] = domain_hint
        if user_id:
            payload["user_id"] = user_id
        
        stream_timeout = timeout or self.config.stream_timeout
        
        try:
            async with self.client.stream(
                "POST",
                "/runs/stream",
                json=payload,
                timeout=stream_timeout,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    raw = line[6:].strip()
                    if not raw:
                        continue
                    
                    try:
                        data = json.loads(raw)
                        yield EventData(
                            event_type=data.get("eventType", data.get("type", "unknown")),
                            payload=data.get("payload", data),
                            timestamp=data.get("timestamp"),
                            run_id=data.get("runId"),
                        )
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse event: {raw}")
                        
        except httpx.HTTPStatusError as e:
            raise ExecutionError(
                f"Task execution failed: {e}",
            )
        except httpx.TimeoutException:
            raise ExecutionError(
                f"Task execution timed out after {stream_timeout}s",
            )
    
    # =========================================================================
    # User & Account Management
    # =========================================================================

    async def list_users(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """
        List all registered users with pagination.

        Args:
            limit: Maximum number of users to return (default: 100)
            offset: Number of users to skip (default: 0)

        Returns:
            PaginatedResponse containing UserInfo objects

        Example:
            >>> users = await client.list_users(limit=50)
            >>> for user in users.items:
            ...     print(user.user_id, user.wallet_address)
            >>> if users.has_more:
            ...     next_users = await client.list_users(offset=users.next_offset)
        """
        response = await self.client.get(
            "/accounts/users",
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        data = response.json()

        users = [UserInfo.from_dict(user) for user in data["users"]]

        return PaginatedResponse(
            items=users,
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )
    
    async def register_user(
        self,
        wallet_address: str,
        *,
        email: Optional[str] = None,
        private_key: Optional[str] = None,
        chain_id: int = 97,
    ) -> Dict[str, Any]:
        """
        Register a new user.
        
        Args:
            wallet_address: User's wallet address
            email: Optional email address
            private_key: Optional private key for on-chain operations
            chain_id: Blockchain chain ID (default: 97 for BSC testnet)
            
        Returns:
            User registration result
        """
        if private_key:
            response = await self.client.post(
                "/accounts/users/register-with-key",
                json={
                    "wallet_address": wallet_address,
                    "private_key": private_key,
                    "email": email,
                    "chain_id": chain_id,
                },
            )
        else:
            response = await self.client.post(
                "/accounts/users/register",
                json={
                    "wallet_address": wallet_address,
                    "email": email,
                },
            )
        response.raise_for_status()
        return response.json()
    
    async def get_user_balance(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's balance.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Balance information
        """
        response = await self.client.get(f"/accounts/users/{user_id}/balance")
        response.raise_for_status()
        return response.json()
    
    # =========================================================================
    # Pricing Operations
    # =========================================================================

    async def get_agent_price(
        self,
        user_id: str,
        agent_id: str,
    ) -> PriceInfo:
        """
        Get pricing for a specific agent owned by a user.

        Args:
            user_id: The user ID who owns the agent
            agent_id: The agent ID

        Returns:
            PriceInfo with pricing details

        Example:
            >>> price = await client.get_agent_price("user:0x123...", "erc8004:my_agent")
            >>> print(f"${price.amount} {price.currency}")
        """
        response = await self.client.get(
            f"/users/{user_id}/agents/{agent_id}/pricing"
        )
        response.raise_for_status()
        return PriceInfo.from_dict(response.json())

    async def update_agent_price(
        self,
        user_id: str,
        agent_id: str,
        amount: float,
        *,
        currency: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PriceInfo:
        """
        Update pricing for a specific agent owned by a user.

        Args:
            user_id: The user ID who owns the agent
            agent_id: The agent ID
            amount: New price amount
            currency: Price currency (optional)
            metadata: Additional metadata (optional)

        Returns:
            Updated PriceInfo

        Example:
            >>> price = await client.update_agent_price(
            ...     "user:0x123...",
            ...     "erc8004:my_agent",
            ...     0.002,
            ...     currency="USD"
            ... )
        """
        payload = {
            "identifier": agent_id,
            "amount": amount,
        }
        if currency:
            payload["currency"] = currency
        if metadata:
            payload["metadata"] = metadata

        response = await self.client.put(
            f"/users/{user_id}/agents/{agent_id}/pricing",
            json=payload,
        )
        response.raise_for_status()
        return PriceInfo.from_dict(response.json())

    async def list_agent_prices(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """
        List agent prices with pagination.

        Args:
            limit: Maximum number of prices to return (default: 100)
            offset: Number of prices to skip (default: 0)

        Returns:
            PaginatedResponse containing PriceInfo objects

        Example:
            >>> prices = await client.list_agent_prices(limit=50)
            >>> for price in prices.items:
            ...     print(f"{price.identifier}: ${price.amount}")
        """
        response = await self.client.get(
            "/pricing/agents",
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        data = response.json()

        prices = [PriceInfo.from_dict(p) for p in data["prices"]]

        return PaginatedResponse(
            items=prices,
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )
    
    # =========================================================================
    # Run Management
    # =========================================================================

    async def list_user_runs(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """
        List runs for a specific user with pagination.

        Args:
            user_id: The user's ID
            limit: Maximum number of runs to return (default: 100)
            offset: Number of runs to skip (default: 0)

        Returns:
            PaginatedResponse containing run information

        Example:
            >>> runs = await client.list_user_runs("user:0x123...", limit=20)
            >>> for run in runs.items:
            ...     print(f"Run {run['run_id']}: {run.get('status', 'unknown')}")
        """
        response = await self.client.get(
            f"/users/{user_id}/runs",
            params={"limit": limit, "offset": offset},
        )
        response.raise_for_status()
        data = response.json()

        return PaginatedResponse(
            items=data["runs"],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )
    
    async def get_run_events(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get events for a specific run.
        
        Args:
            run_id: The run ID
            
        Returns:
            List of events
        """
        response = await self.client.get(f"/runs/{run_id}/events")
        response.raise_for_status()
        return response.json()
    
    async def get_run_payments(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get payments for a specific run.
        
        Args:
            run_id: The run ID
            
        Returns:
            List of payments
        """
        response = await self.client.get(f"/runs/{run_id}/payments")
        response.raise_for_status()
        return response.json()
    
    # =========================================================================
    # Memory Operations
    # =========================================================================

    async def list_memory_scopes(self) -> List[str]:
        """
        List memory scopes.

        Returns:
            List of scope names
        """
        response = await self.client.get("/memory")
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    async def get_memory(self, scope: str) -> Dict[str, Any]:
        """
        Get memory contents for a scope.

        Args:
            scope: Memory scope name

        Returns:
            Memory contents
        """
        response = await self.client.get(f"/memory/{scope}")
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Agent Communication
    # =========================================================================

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message: Dict[str, Any],
        protocol: str = "aip"
    ) -> Dict[str, Any]:
        """
        Send a message from one agent to another.

        Args:
            from_agent: Sender agent ID
            to_agent: Receiver agent ID
            message: Message content (arbitrary dict)
            protocol: Communication protocol (default: "aip")

        Returns:
            Message delivery response

        Example:
            >>> response = await client.send_message(
            ...     from_agent="agent_abc123",
            ...     to_agent="agent_def456",
            ...     message={"type": "question", "content": "Hello!"}
            ... )
        """
        response = await self.client.post(
            "/messages/send",
            json={
                "from": from_agent,
                "to": to_agent,
                "message": message,
                "protocol": protocol
            }
        )
        response.raise_for_status()
        return response.json()

    async def update_agent_metadata(
        self,
        agent_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Update agent metadata.

        Args:
            agent_id: Agent ID
            metadata: Metadata fields to update

        Example:
            >>> await client.update_agent_metadata(
            ...     agent_id="agent_abc123",
            ...     metadata={"version": "2.0", "capabilities": ["nlp", "vision"]}
            ... )
        """
        response = await self.client.patch(
            f"/agents/{agent_id}",
            json={"metadata": metadata}
        )
        response.raise_for_status()


class AIPClient:
    """
    Synchronous wrapper around AsyncAIPClient.
    
    Example:
        client = AIPClient("http://localhost:8001")
        
        # List agents
        agents = client.list_agents()
        
        # Run a task
        result = client.run("What's the weather?")
        print(result.output)
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        *,
        timeout: float = 60.0,
        stream_timeout: float = 300.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the AIP client.
        
        Args:
            base_url: Base URL of the AIP platform
            timeout: Default timeout for requests
            stream_timeout: Timeout for streaming requests
            headers: Additional headers to include in requests
        """
        self._async_client = AsyncAIPClient(
            base_url=base_url,
            timeout=timeout,
            stream_timeout=stream_timeout,
            headers=headers,
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
            return self._loop
    
    def _run(self, coro):
        """Run a coroutine synchronously."""
        loop = self._get_loop()
        try:
            return loop.run_until_complete(coro)
        except RuntimeError:
            # Already running in an event loop
            return asyncio.ensure_future(coro)
    
    def close(self) -> None:
        """Close the client connection."""
        self._run(self._async_client.close())
        if self._loop and not self._loop.is_closed():
            self._loop.close()
    
    def __enter__(self) -> "AIPClient":
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
    
    # Delegate methods to async client

    def health_check(self) -> bool:
        """Check if the AIP platform is healthy."""
        return self._run(self._async_client.health_check())

    def wait_for_ready(
        self,
        max_attempts: int = 30,
        interval: float = 1.0,
    ) -> bool:
        """Wait for the AIP platform to be ready."""
        return self._run(self._async_client.wait_for_ready(max_attempts, interval))

    # Agent Operations

    def list_user_agents(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List agents owned by a specific user with pagination."""
        return self._run(self._async_client.list_user_agents(user_id, limit=limit, offset=offset))

    def get_agent(self, user_id: str, agent_id: str) -> Optional[AgentInfo]:
        """Get information about a specific agent owned by a user."""
        return self._run(self._async_client.get_agent(user_id, agent_id))

    def register_agent(
        self,
        user_id: str,
        agent: Union[SDKAgent, AgentConfig, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Register an agent for a specific user."""
        return self._run(self._async_client.register_agent(user_id, agent))

    def unregister_agent(
        self,
        user_id: str,
        agent_id: str,
    ) -> Dict[str, Any]:
        """Unregister an agent owned by a user."""
        return self._run(self._async_client.unregister_agent(user_id, agent_id))

    def register(
        self,
        user_id: str,
        agent: Union[SDKAgent, AgentConfig],
    ) -> Dict[str, Any]:
        """Alias for register_agent."""
        return self._run(self._async_client.register(user_id, agent))
    
    def run(
        self,
        objective: str,
        *,
        domain_hint: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> RunResult:
        return self._run(self._async_client.run(
            objective,
            domain_hint=domain_hint,
            user_id=user_id,
            timeout=timeout,
        ))
    
    # User Management

    def list_users(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List all registered users with pagination."""
        return self._run(self._async_client.list_users(limit=limit, offset=offset))

    def register_user(
        self,
        wallet_address: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Register a new user."""
        return self._run(self._async_client.register_user(wallet_address, **kwargs))

    def get_user_balance(self, user_id: str) -> Dict[str, Any]:
        """Get user's balance."""
        return self._run(self._async_client.get_user_balance(user_id))

    # Pricing Operations

    def get_agent_price(
        self,
        user_id: str,
        agent_id: str,
    ) -> PriceInfo:
        """Get pricing for a specific agent owned by a user."""
        return self._run(self._async_client.get_agent_price(user_id, agent_id))

    def update_agent_price(
        self,
        user_id: str,
        agent_id: str,
        amount: float,
        **kwargs,
    ) -> PriceInfo:
        """Update pricing for a specific agent owned by a user."""
        return self._run(self._async_client.update_agent_price(user_id, agent_id, amount, **kwargs))

    def list_agent_prices(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List agent prices with pagination."""
        return self._run(self._async_client.list_agent_prices(limit=limit, offset=offset))

    # Run Management

    def list_user_runs(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List runs for a specific user with pagination."""
        return self._run(self._async_client.list_user_runs(user_id, limit=limit, offset=offset))

    def get_run_events(self, run_id: str) -> List[Dict[str, Any]]:
        """Get events for a specific run."""
        return self._run(self._async_client.get_run_events(run_id))

    def get_run_payments(self, run_id: str) -> List[Dict[str, Any]]:
        """Get payments for a specific run."""
        return self._run(self._async_client.get_run_payments(run_id))

    # Agent Communication

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message: Dict[str, Any],
        protocol: str = "aip"
    ) -> Dict[str, Any]:
        """Send a message from one agent to another."""
        return self._run(self._async_client.send_message(from_agent, to_agent, message, protocol))

    def update_agent_metadata(
        self,
        agent_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Update agent metadata."""
        return self._run(self._async_client.update_agent_metadata(agent_id, metadata))


# Convenience function for quick client creation
def create_client(
    base_url: str = "http://localhost:8001",
    **kwargs,
) -> AIPClient:
    """
    Create an AIP client.
    
    Args:
        base_url: Base URL of the AIP platform
        **kwargs: Additional client configuration
        
    Returns:
        AIPClient instance
    """
    return AIPClient(base_url, **kwargs)


@asynccontextmanager
async def async_client(
    base_url: str = "http://localhost:8001",
    **kwargs,
) -> AsyncGenerator[AsyncAIPClient, None]:
    """
    Create an async AIP client as a context manager.
    
    Args:
        base_url: Base URL of the AIP platform
        **kwargs: Additional client configuration
        
    Yields:
        AsyncAIPClient instance
    """
    client = AsyncAIPClient(base_url, **kwargs)
    try:
        yield client
    finally:
        await client.close()

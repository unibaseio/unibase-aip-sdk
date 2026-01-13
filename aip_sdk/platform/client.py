"""AIP Client Module."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Union,
)

import httpx

from aip_sdk.types import (
    AgentConfig,
    AgentGroupConfig,
    AgentInfo,
    EventData,
    RunResult,
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

logger = logging.getLogger(__name__)


def _get_default_base_url() -> str:
    """Get default base URL from AIP_ENDPOINT environment variable."""
    import os
    url = os.environ.get("AIP_ENDPOINT")
    if url:
        return url.rstrip("/")
    return "http://localhost:8001"


@dataclass
class ClientConfig:
    """Configuration for the AIP client."""
    base_url: str = None  # Will be set in __post_init__
    timeout: float = 60.0
    stream_timeout: float = 300.0
    max_retries: int = 3
    retry_delay: float = 1.0
    headers: Dict[str, str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.base_url is None:
            self.base_url = _get_default_base_url()


class AsyncAIPClient:
    """Async client for interacting with the AIP platform."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        timeout: float = 60.0,
        stream_timeout: float = 300.0,
        headers: Optional[Dict[str, str]] = None,
        config: Optional[ClientConfig] = None,
    ):
        """Initialize the async AIP client."""
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
    
    async def health_check(self) -> bool:
        """Check if the AIP platform is healthy."""
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
        """Wait for the AIP platform to be ready."""
        for _ in range(max_attempts):
            if await self.health_check():
                return True
            await asyncio.sleep(interval)
        return False

    async def list_user_agents(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List agents owned by a specific user with pagination."""
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
        """Get information about a specific agent owned by a user."""
        agents_response = await self.list_user_agents(user_id, limit=1000)
        for agent in agents_response.items:
            if agent.agent_id == agent_id:
                return agent
        return None

    async def register_agent(
        self,
        user_id: str,
        agent: Union[AgentConfig, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Register an agent for a specific user."""
        if isinstance(agent, AgentConfig):
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
        """Unregister an agent owned by a user."""
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

    async def register_agent_group(
        self,
        group: Union[AgentGroupConfig, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Register an agent group.
        """
        if isinstance(group, AgentGroupConfig):
            reg_data = group.to_registration_dict()
        else:
            reg_data = group

        try:
            response = await self.client.post(
                "/agents/groups/register",
                json=reg_data,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise RegistrationError(
                f"Failed to register agent group '{reg_data.get('group_name')}': {e}",
                handle=reg_data.get("group_name"),
            )

    async def run(
        self,
        objective: str,
        *,
        agent: Optional[str] = None,
        domain_hint: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> RunResult:
        """Execute a task and return the final result."""
        events: List[EventData] = []
        payments: List[Dict[str, Any]] = []
        result = None
        error = None
        run_id = None

        try:
            async for event in self.run_stream(
                objective,
                agent=agent,
                domain_hint=domain_hint,
                user_id=user_id,
                timeout=timeout,
            ):
                events.append(event)
                run_id = run_id or event.run_id

                if "payment" in event.event_type.lower():
                    payment_data = {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                    }
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
        agent: Optional[str] = None,
        domain_hint: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[EventData, None]:
        """Execute a task and stream events."""
        payload: Dict[str, Any] = {"objective": objective}
        if agent:
            payload["agent"] = agent
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

    async def list_users(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List all registered users with pagination."""
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
        """Register a new user."""
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

    async def get_agent_price(
        self,
        user_id: str,
        agent_id: str,
    ) -> PriceInfo:
        """Get pricing for a specific agent owned by a user."""
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
        """Update pricing for a specific agent owned by a user."""
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
        """List agent prices with pagination."""
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

    async def list_user_runs(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List runs for a specific user with pagination."""
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
        """Get events for a specific run."""
        response = await self.client.get(f"/runs/{run_id}/events")
        response.raise_for_status()
        return response.json()
    
    async def get_run_payments(self, run_id: str) -> List[Dict[str, Any]]:
        """Get payments for a specific run."""
        response = await self.client.get(f"/runs/{run_id}/payments")
        response.raise_for_status()
        return response.json()
    
class AIPClient:
    """Synchronous wrapper around AsyncAIPClient."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        timeout: float = 60.0,
        stream_timeout: float = 300.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize the AIP client."""
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
        agent: Union[AgentConfig, Dict[str, Any]],
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

    def run(
        self,
        objective: str,
        *,
        agent: Optional[str] = None,
        domain_hint: Optional[str] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> RunResult:
        return self._run(self._async_client.run(
            objective,
            agent=agent,
            domain_hint=domain_hint,
            user_id=user_id,
            timeout=timeout,
        ))

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

"""Gateway Client for AIP SDK."""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


def _get_default_gateway_url() -> str:
    """Get default gateway URL from GATEWAY_URL environment variable."""
    url = os.environ.get("GATEWAY_URL")
    if url:
        return url.rstrip("/")
    return "http://localhost:8080"


class GatewayClient:
    """Client for interacting with the Agent Gateway."""

    def __init__(self, gateway_url: Optional[str] = None, timeout: float = 10.0):
        """Initialize gateway client."""
        self.gateway_url = (gateway_url or _get_default_gateway_url()).rstrip('/')
        self.timeout = timeout

    async def register_agent(
        self,
        agent_name: str,
        backend_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Register an agent with the gateway."""
        url = f"{self.gateway_url}/gateway/register"
        payload = {
            "agent_name": agent_name,
            "backend_url": backend_url,
            "metadata": metadata or {},
            "force": force
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            logger.info(
                f"Registered agent '{agent_name}' with gateway: {result['gateway_url']}"
            )
            return result

    async def unregister_agent(self, agent_name: str) -> Dict[str, Any]:
        """Unregister an agent from the gateway."""
        url = f"{self.gateway_url}/gateway/unregister/{agent_name}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            logger.info(f"Unregistered agent '{agent_name}' from gateway")
            return result

    async def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents."""
        url = f"{self.gateway_url}/gateway/agents"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            return result.get("agents", [])

    async def get_agent_info(self, agent_name: str) -> Dict[str, Any]:
        """Get information about a specific agent."""
        url = f"{self.gateway_url}/gateway/agents/{agent_name}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """Check if gateway is reachable and healthy."""
        url = f"{self.gateway_url}/gateway/health"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                return data.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Gateway health check failed: {e}")
            return False

    async def wait_for_gateway(self, max_attempts: int = 30, interval: float = 1.0) -> bool:
        """Wait for gateway to become available."""
        import asyncio

        for attempt in range(max_attempts):
            if await self.health_check():
                logger.info(f"Gateway is available at {self.gateway_url}")
                return True

            if attempt < max_attempts - 1:
                await asyncio.sleep(interval)

        logger.error(f"Gateway not available after {max_attempts} attempts")
        return False


# Synchronous wrapper for convenience
class SyncGatewayClient:
    """Synchronous wrapper for GatewayClient."""

    def __init__(self, gateway_url: str, timeout: float = 10.0):
        """Initialize synchronous gateway client."""
        self.client = GatewayClient(gateway_url, timeout)

    def register_agent(
        self,
        agent_name: str,
        backend_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Register an agent (sync version)."""
        import asyncio
        return asyncio.run(
            self.client.register_agent(agent_name, backend_url, metadata, force)
        )

    def unregister_agent(self, agent_name: str) -> Dict[str, Any]:
        """Unregister an agent (sync version)."""
        import asyncio
        return asyncio.run(self.client.unregister_agent(agent_name))

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all agents (sync version)."""
        import asyncio
        return asyncio.run(self.client.list_agents())

    def get_agent_info(self, agent_name: str) -> Dict[str, Any]:
        """Get agent info (sync version)."""
        import asyncio
        return asyncio.run(self.client.get_agent_info(agent_name))

    def health_check(self) -> bool:
        """Health check (sync version)."""
        import asyncio
        return asyncio.run(self.client.health_check())

    def wait_for_gateway(self, max_attempts: int = 30, interval: float = 1.0) -> bool:
        """Wait for gateway (sync version)."""
        import asyncio
        return asyncio.run(self.client.wait_for_gateway(max_attempts, interval))

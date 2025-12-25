"""
Gateway Client for AIP SDK

Helper utilities for agents to register with a gateway.

Example:
    from aip_sdk.gateway_client import GatewayClient

    client = GatewayClient("http://localhost:8080")
    result = await client.register_agent("calculator", "http://localhost:8103")
    print(f"Agent accessible at: {result['gateway_url']}")
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class GatewayClient:
    """Client for interacting with the Agent Gateway."""

    def __init__(self, gateway_url: str, timeout: float = 10.0):
        """
        Initialize gateway client.

        Args:
            gateway_url: Base URL of the gateway (e.g., http://localhost:8080)
            timeout: Request timeout in seconds
        """
        self.gateway_url = gateway_url.rstrip('/')
        self.timeout = timeout

    async def register_agent(
        self,
        agent_name: str,
        backend_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Register an agent with the gateway.

        Args:
            agent_name: Unique agent identifier
            backend_url: Backend agent URL (e.g., http://localhost:8103)
            metadata: Optional metadata dictionary
            force: Force re-registration if agent already exists

        Returns:
            Registration response with gateway_url and path

        Raises:
            httpx.HTTPStatusError: If registration fails
        """
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
        """
        Unregister an agent from the gateway.

        Args:
            agent_name: Agent identifier to unregister

        Returns:
            Unregistration response

        Raises:
            httpx.HTTPStatusError: If unregistration fails
        """
        url = f"{self.gateway_url}/gateway/unregister/{agent_name}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(url, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            logger.info(f"Unregistered agent '{agent_name}' from gateway")
            return result

    async def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all registered agents.

        Returns:
            List of agent information dictionaries

        Raises:
            httpx.HTTPStatusError: If request fails
        """
        url = f"{self.gateway_url}/gateway/agents"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()

            return result.get("agents", [])

    async def get_agent_info(self, agent_name: str) -> Dict[str, Any]:
        """
        Get information about a specific agent.

        Args:
            agent_name: Agent identifier

        Returns:
            Agent information dictionary

        Raises:
            httpx.HTTPStatusError: If request fails or agent not found
        """
        url = f"{self.gateway_url}/gateway/agents/{agent_name}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """
        Check if gateway is reachable and healthy.

        Returns:
            True if gateway is healthy, False otherwise
        """
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
        """
        Wait for gateway to become available.

        Args:
            max_attempts: Maximum number of attempts
            interval: Seconds between attempts

        Returns:
            True if gateway became available, False if timeout
        """
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

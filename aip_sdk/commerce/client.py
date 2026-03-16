from typing import Any, Dict, Optional, List
from ..platform.client import AsyncAIPClient

class MissionClient:
    """Specialized client for Agentic Commerce (Missions)."""

    def __init__(self, aip_client: AsyncAIPClient):
        self.aip = aip_client

    async def create(
        self,
        client_id: str,
        description: str,
        reward_amount: float,
        reward_token: str,
        evaluator_id: str,
        expires_in: int = 86400,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new mission."""
        return await self.aip.create_mission(
            client_id=client_id,
            description=description,
            reward_amount=reward_amount,
            reward_token=reward_token,
            evaluator_id=evaluator_id,
            expires_in=expires_in,
            metadata=metadata
        )

    async def accept(self, mission_id: str, provider_id: str) -> bool:
        """Accept a mission. Returns True if successful."""
        result = await self.aip.accept_mission(mission_id, provider_id)
        return result.get("status") == "accepted"

    async def submit(
        self,
        mission_id: str,
        provider_id: str,
        deliverable_data: Any,
        description: str = "",
    ) -> bool:
        """Submit work for a mission. Returns True if successful."""
        result = await self.aip.submit_mission_work(
            mission_id=mission_id,
            provider_id=provider_id,
            deliverable_data=deliverable_data,
            description=description
        )
        return result.get("status") == "submitted"

    async def complete(
        self,
        mission_id: str,
        evaluator_id: str,
        reason: str = "",
    ) -> bool:
        """Complete a mission (as evaluator). Returns True if successful."""
        result = await self.aip.complete_mission(
            mission_id=mission_id,
            evaluator_id=evaluator_id,
            reason=reason
        )
        return result.get("status") == "completed"

    async def get(self, mission_id: str) -> Dict[str, Any]:
        """Get mission details and current status."""
        return await self.aip.get_mission(mission_id)

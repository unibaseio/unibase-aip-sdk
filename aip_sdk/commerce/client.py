from typing import Any, Dict, Optional, List
from ..platform.client import AsyncAIPClient

class JobClient:
    """Specialized client for Agentic Commerce (Jobs)."""

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
        """Create a new job."""
        return await self.aip.create_job(
            client_id=client_id,
            description=description,
            reward_amount=reward_amount,
            reward_token=reward_token,
            evaluator_id=evaluator_id,
            expires_in=expires_in,
            metadata=metadata
        )

    async def accept(self, job_id: str, provider_id: str) -> bool:
        """Accept a job. Returns True if successful."""
        result = await self.aip.accept_job(job_id, provider_id)
        return result.get("status") == "accepted"

    async def submit(
        self,
        job_id: str,
        provider_id: str,
        deliverable_data: Any,
        description: str = "",
    ) -> bool:
        """Submit work for a job. Returns True if successful."""
        result = await self.aip.submit_job_work(
            job_id=job_id,
            provider_id=provider_id,
            deliverable_data=deliverable_data,
            description=description
        )
        return result.get("status") == "submitted"

    async def complete(
        self,
        job_id: str,
        evaluator_id: str,
        reason: str = "",
    ) -> bool:
        """Complete a job (as evaluator). Returns True if successful."""
        result = await self.aip.complete_job(
            job_id=job_id,
            evaluator_id=evaluator_id,
            reason=reason
        )
        return result.get("status") == "completed"

    async def get(self, job_id: str) -> Dict[str, Any]:
        """Get job list and current status."""
        return await self.aip.get_job(job_id)

import json
import logging
from typing import Any, Dict, Optional
from aip_sdk.commerce.client import MissionClient

logger = logging.getLogger(__name__)

class SchemaEvaluator:
    """
    Tier 2 Evaluator: Automatically verifies mission deliverables against a JSON Schema.
    This mimics the standardized verification logic seen in platforms like Virtuals.
    """

    def __init__(self, mission_market: MissionClient, evaluator_id: str):
        self.market = mission_market
        self.evaluator_id = evaluator_id

    async def verify_and_settle(
        self, 
        mission_id: str, 
        requirement_schema: Dict[str, Any],
        deliverable_schema: Dict[str, Any]
    ) -> bool:
        """
        Fetches the mission, validates the deliverable data, 
        and triggers on-chain completion/rejection.
        """
        try:
            # 1. Fetch current mission state
            mission = await self.market.get(mission_id)
            if mission["status"] != "submitted":
                logger.warning(f"Mission {mission_id} is not in 'submitted' state. Current: {mission['status']}")
                return False

            # In a real scenario, the deliverable data might be fetched from a URI.
            # Here we assume the AIP platform stores/returns the structured metadata.
            deliverable_data = mission.get("metadata", {}).get("deliverable_data")
            
            if not deliverable_data:
                await self._reject(mission_id, "Missing deliverable data in mission metadata.")
                return False

            # 2. Perform Validation (Simplified JSON check for demo)
            # In production, use 'jsonschema' library: validate(instance=deliverable_data, schema=deliverable_schema)
            is_valid = self._validate_data(deliverable_data, deliverable_schema)

            if is_valid:
                logger.info(f"Mission {mission_id} passed verification.")
                return await self.market.complete(
                    mission_id=mission_id,
                    evaluator_id=self.evaluator_id,
                    reason="Automated verification successful: Deliverable matches required schema."
                )
            else:
                logger.warning(f"Mission {mission_id} failed verification.")
                return await self._reject(mission_id, "Deliverable does not match the required schema.")

        except Exception as e:
            logger.error(f"Error during automated evaluation: {e}")
            return False

    def _validate_data(self, data: Any, schema: Dict[str, Any]) -> bool:
        """Basic type and key presence validation (MVP logic)."""
        # Example schema: {"type": "object", "required": ["tx_hash"]}
        if schema.get("type") == "object" and not isinstance(data, dict):
            return False
        
        for key in schema.get("required", []):
            if key not in data:
                return False
        
        return True

    async def _reject(self, mission_id: str, reason: str) -> bool:
        return await self.market.aip.client.post(
            f"/v1/missions/{mission_id}/reject?rejector_id={self.evaluator_id}",
            json={"reason": reason}
        )

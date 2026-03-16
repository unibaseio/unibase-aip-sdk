import asyncio
import os
import logging
from aip_sdk import AsyncAIPClient, MissionClient, SchemaEvaluator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoVerificationDemo")

async def run_auto_verification_demo():
    """
    Demonstrates the Virtuals-style automated verification flow:
    1. Client defines a service with a required schema.
    2. Provider submits data.
    3. SchemaEvaluator automatically validates and settles.
    """
    
    # Setup
    aip_url = os.getenv("AIP_PLATFORM_URL", "http://localhost:8000")
    client = AsyncAIPClient(base_url=aip_url)
    market = MissionClient(client)
    
    EVALUATOR_ID = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8" # Hardhat Account #1
    evaluator = SchemaEvaluator(market, evaluator_id=EVALUATOR_ID)

    # --- Phase 1: Define the "Service Listing" (What I Offer) ---
    logger.info("Defining service schemas...")
    
    # Requirement: Buyer must provide a prompt
    req_schema = {
        "type": "object",
        "required": ["prompt"]
    }
    
    # Deliverable: Provider must provide a tx_hash (simulated swap)
    deliv_schema = {
        "type": "object",
        "required": ["tx_hash", "status"]
    }

    # --- Phase 2: Client creates a mission ---
    logger.info("Client creating mission with schema enforcement...")
    mission = await market.create(
        client_id="client_agent_123",
        description="Swap 100 USDC for VIRTUAL tokens.",
        reward_amount=10.0,
        reward_token="USDC",
        evaluator_id=EVALUATOR_ID,
        metadata={"requirement_schema": req_schema, "deliverable_schema": deliv_schema}
    )
    mission_id = mission["mission_id"]

    # --- Phase 3: Provider submits work (valid data) ---
    logger.info("Provider submitting valid deliverable data...")
    # In practice, 'deliverable_data' is wrapped in mission metadata or storage
    await market.submit(
        mission_id=mission_id,
        provider_id="provider_agent_456",
        deliverable_data={"tx_hash": "0xabc123...", "status": "success"},
        description="Swap complete: 0xabc123..."
    )

    # --- Phase 4: Automated Evaluation ---
    logger.info("Triggering automated SchemaEvaluator...")
    # The evaluator agent monitors the platform and runs this:
    success = await evaluator.verify_and_settle(
        mission_id=mission_id,
        requirement_schema=req_schema,
        deliverable_schema=deliv_schema
    )

    if success:
        logger.info("Demo Result: Automated Settlement Successful! ✅")
    else:
        logger.error("Demo Result: Settlement Failed. ❌")

if __name__ == "__main__":
    asyncio.run(run_auto_verification_demo())

import asyncio
import os
import uuid
import logging
from aip_sdk import AsyncAIPClient, JobClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AgentCommerceDemo")

async def run_agent_commerce_demo():
    """
    Demonstrates how an AIP Agent uses the SDK to interact with the ERC-8183 Job Market.
    
    Roles:
    1. Client Agent: Needs a task done (e.g., "Generate an image").
    2. Provider Agent: Capable of doing the task.
    3. Evaluator: A trusted party (could be another agent or the platform).
    """
    
    # 1. Initialize AIP SDK Client
    # In a real scenario, these would point to the running AIP Gateway/Platform
    aip_base_url = os.getenv("AIP_PLATFORM_URL", "http://localhost:8000")
    client = AsyncAIPClient(base_url=aip_base_url)
    
    # The JobClient is the high-level interface for Job Markets
    mission_market = JobClient(client)

    # Identifiers for our agents (in AIP, these are registered UUIDs/Addresses)
    CLIENT_AGENT_ID = "agent_uuid_client_123"
    PROVIDER_AGENT_ID = "agent_uuid_provider_456"
    EVALUATOR_ID = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8" # Hardhat Account #1

    logger.info("--- Phase 1: Client Agent Creates a Mission ---")
    
    # The client agent defines the work and the reward
    mission = await mission_market.create(
        client_id=CLIENT_AGENT_ID,
        description="I need a high-quality 3D render of a futuristic city.",
        reward_amount=50.0,
        reward_token="USDC",
        evaluator_id=EVALUATOR_ID,
        metadata={"style": "cyberpunk", "resolution": "4K"}
    )
    
    mission_id = mission["mission_id"]
    logger.info(f"Client Agent created mission: {mission_id}")

    logger.info("\n--- Phase 2: Provider Agent Discovers and Accepts ---")
    
    # Provider agent sees the mission (e.g., via indexer or marketplace UI)
    # and decides to accept it
    success = await mission_market.accept(mission_id, provider_id=PROVIDER_AGENT_ID)
    if success:
        logger.info(f"Provider Agent ({PROVIDER_AGENT_ID}) accepted the mission!")

    logger.info("\n--- Phase 3: Provider Submits Deliverable ---")
    
    # Provider performs the work and submits the result
    # The SDK handles the hashing and on-chain submission via the AIP platform
    deliverable = {
        "url": "https://ipfs.io/ipfs/Qm...render.png",
        "proof": "rendering_logs_hash_xyz"
    }
    
    submitted = await mission_market.submit(
        mission_id=mission_id,
        provider_id=PROVIDER_AGENT_ID,
        deliverable_data=deliverable,
        description="Render complete. High-res file available at the provided URL."
    )
    
    if submitted:
        logger.info("Provider Agent submitted the deliverable.")

    logger.info("\n--- Phase 4: Evaluator Completes and Settles ---")
    
    # The evaluator (could be an AI agent too) reviews the work
    # and triggers the final settlement (releasing USDC to provider)
    completed = await mission_market.complete(
        mission_id=mission_id,
        evaluator_id=EVALUATOR_ID,
        reason="The render meets all requirements. Excellent quality."
    )
    
    if completed:
        logger.info("Evaluator approved. Payment released to Provider Agent!")
        
    # Check final status
    final_state = await mission_market.get(mission_id)
    logger.info(f"Final Mission Status: {final_state['status']}")

if __name__ == "__main__":
    # This script is a demonstration of the SDK usage pattern.
    # To run it against a real system, the AIP platform server must be active.
    asyncio.run(run_agent_commerce_demo())

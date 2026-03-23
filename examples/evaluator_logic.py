import asyncio
import hashlib
from aip_sdk import AsyncAIPClient, MissionClient

async def auto_verify_agent_work(mission_id: str, evaluator_key: str):
    """
    Example of an 'AI Evaluator' that automatically verifies work.
    This evaluator monitors for 'Submitted' missions, runs verification logic,
    and calls 'complete' or 'reject' on the ERC-8183 market.
    """
    aip = AsyncAIPClient()
    market = MissionClient(aip)

    # 1. Fetch mission details
    mission = await market.get(mission_id)
    if mission["status"] != "submitted":
        print("Mission not in submitted state.")
        return

    # 2. Retrieve the deliverable data (off-chain)
    # The deliverable_uri points to where the actual work is stored (e.g., IPFS, S3, Membase)
    deliverable_uri = mission.get("deliverable_uri")
    deliverable_hash = mission.get("deliverable_hash")
    
    print(f"Verifying work at: {deliverable_uri}")
    
    # --- AUTOMATED VERIFICATION LOGIC ---
    # Here, the evaluator agent (or a script) performs the check:
    # - If it's code: run unit tests.
    # - If it's an image: run CLIP/Aesthetics scoring or check dimensions.
    # - If it's a swap: check the chain for the transaction hash.
    
    is_valid = True # Placeholder for actual logic
    
    # Optional: Verify the local file hash matches the on-chain hash
    # content = download(deliverable_uri)
    # assert hashlib.sha256(content).hexdigest() == deliverable_hash
    
    # 3. Finalize on-chain settlement
    if is_valid:
        print("Verification passed! Releasing payment...")
        await market.complete(
            mission_id=mission_id,
            evaluator_id="evaluator_address",
            reason="Verified: Deliverable matches requirements and hash is valid."
        )
    else:
        print("Verification failed! Rejecting...")
        await market.reject(
            mission_id=mission_id,
            rejector_id="evaluator_address",
            reason="Failed: Quality below threshold or invalid format."
        )

if __name__ == "__main__":
    # This logic represents the 'Brain' of the Evaluator role.
    # It bridges the gap between off-chain output and on-chain money.
    pass

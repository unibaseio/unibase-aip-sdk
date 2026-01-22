#!/usr/bin/env python3
"""
Example: List and query agents via AIP SDK

This example shows how to use the AIP SDK to:
- List all agents with pagination
- Get agent details
- Check agent pricing

Prerequisites:
- Install: uv pip install -e .

Environment Variables:
- AIP_ENDPOINT: AIP platform URL (default: http://localhost:8001)
  For production: export AIP_ENDPOINT=http://api.aip.unibase.com
- TEST_WALLET: Wallet address for testing (default: 0x5ea13664c5ce67753f208540d25b913788aa3daa)
"""

import asyncio
import os
from aip_sdk import AsyncAIPClient


async def main():
    """List agents from the AIP platform."""

    print("Connecting to AIP Platform...")

    # AsyncAIPClient auto-detects URL from environment variables
    async with AsyncAIPClient() as client:
        # Check health first
        if not await client.health_check():
            print("Platform not available")
            return

        # Use existing test user (or register if needed)
        # Use the test wallet from environment or default
        test_wallet = os.environ.get("TEST_WALLET", "0x5ea13664c5ce67753f208540d25b913788aa3daa")
        user_id = f"user:{test_wallet}"

        # List agents with pagination
        print("\nAvailable Agents:")
        print("-" * 60)

        offset = 0
        limit = 10

        while True:
            page = await client.list_user_agents(user_id, limit=limit, offset=offset)

            for agent in page.items:
                print(f"  {agent.handle}")
                print(f"    Name: {agent.name}")
                print(f"    Description: {agent.description[:50] if agent.description else 'N/A'}...")
                print()

            if not page.has_more:
                break

            offset = page.next_offset

        print(f"Total: {page.total} agents")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Example: List and query agents via AIP SDK

This example shows how to use the AIP SDK to:
- List all agents with pagination
- Get agent details
- Check agent pricing

Prerequisites:
- AIP platform running (default: http://localhost:8001)

Environment Variables:
- AIP_SDK_BASE_URL: Override the AIP platform URL
- AIP_PUBLIC_URL: Alternative override for AIP platform URL
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

        # Register/get user
        user = await client.register_user(
            wallet_address="0xdemo000000000000000000000000000000000000"
        )
        user_id = user["user_id"]

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

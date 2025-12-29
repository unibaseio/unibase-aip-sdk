#!/usr/bin/env python3
"""
Example: Using AIP SDK Client to interact with Unibase AIP Platform

This example demonstrates how to use the AIP SDK client to:
- Connect to the AIP platform
- Register users and agents
- Run tasks and get results
- Stream task events

Prerequisites:
- AIP platform running (default: http://localhost:8001)
- Install: pip install -e packages/unibase-aip-sdk

Environment Variables:
- AIP_SDK_BASE_URL: Override the AIP platform URL
- AIP_PUBLIC_URL: Alternative override for AIP platform URL
"""

import asyncio
import os
from aip_sdk import AsyncAIPClient, AgentConfig


async def main():
    """Demonstrate AIP SDK client usage."""

    print("=" * 70)
    print("AIP SDK Client Example")
    print("=" * 70)
    print()

    # 1. Connect to AIP platform
    # URL is auto-detected from environment or defaults to localhost
    print("[1/5] Connecting to AIP Platform")
    print("-" * 70)

    # AsyncAIPClient auto-detects URL from AIP_SDK_BASE_URL or AIP_PUBLIC_URL env vars
    async with AsyncAIPClient() as client:
        # Check health
        is_healthy = await client.health_check()
        print(f"  Platform healthy: {is_healthy}")

        if not is_healthy:
            print("  ERROR: Platform not available. Start with ./scripts/start.sh")
            return

        # 2. Register a user
        print()
        print("[2/5] Registering User")
        print("-" * 70)

        user = await client.register_user(
            wallet_address="0x1234567890abcdef1234567890abcdef12345678",
            email="demo@example.com"
        )
        user_id = user.get("user_id")
        print(f"  User ID: {user_id}")

        # 3. List available agents
        print()
        print("[3/5] Listing Available Agents")
        print("-" * 70)

        agents = await client.list_user_agents(user_id, limit=10)
        print(f"  Total agents: {agents.total}")
        for agent in agents.items:
            print(f"    - {agent.handle}: {agent.name}")

        # 4. Run a task
        print()
        print("[4/5] Running a Task")
        print("-" * 70)

        try:
            result = await client.run(
                objective="What is 2 + 2?",
                user_id=user_id,
                timeout=30.0
            )
            print(f"  Success: {result.success}")
            print(f"  Output: {result.output}")
        except Exception as e:
            print(f"  Task failed (no agents available?): {e}")

        # 5. Stream task events (if agents available)
        print()
        print("[5/5] Streaming Task Events")
        print("-" * 70)

        try:
            print("  Streaming events...")
            async for event in client.run_stream(
                objective="Hello, what can you do?",
                user_id=user_id,
                timeout=30.0
            ):
                if event.event_type == "answer_chunk":
                    content = event.payload.get("content", "")
                    print(f"    Chunk: {content[:50]}...")
                elif event.is_completed:
                    print(f"    Completed!")
                    break
        except Exception as e:
            print(f"  Streaming failed: {e}")

    print()
    print("=" * 70)
    print("Example Complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Client Example: Calling Public and Private Agents via AIP Platform

This example demonstrates how to create a client that calls agents through the AIP platform.
Works with both public agents (e.g., weather_public) and private agents (e.g., calculator_private).

Features:
- Call agents by handle through AIP platform
- Stream real-time events
- Automatic X402 payment handling
- Automatic Membase conversation memory

Environment Variables:
- AIP_ENDPOINT=http://api.aip.unibase.com
- MEMBASE_ACCOUNT=0x5ea13664c5ce67753f208540d25b913788aa3daa (test account)
- MEMBASE_SECRET_KEY=<contact us for test account credentials>
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "packages" / "unibase-aip-sdk"))

from aip_sdk import AsyncAIPClient


# ============================================================================
# Example 1: Call Public Weather Agent
# ============================================================================

async def call_weather_agent():
    """Call the public weather agent."""
    print("\n" + "="*70)
    print("Example 1: Calling Public Weather Agent")
    print("="*70)

    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
    user_wallet = os.environ.get("MEMBASE_ACCOUNT", "0x5ea13664c5ce67753f208540d25b913788aa3daa")
    user_id = f"user:0x5eA13664c5ce67753f208540d25B913788Aa3DaA"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        print(f"\nCalling weather_public agent...")
        print(f"Query: What's the weather in Tokyo?")

        result = await client.run(
            objective="What's the weather in Tokyo?",
            agent="weather_public",
            user_id=user_id,
            timeout=30.0,
        )

        print(f"\n✓ Success: {result.success}")
        print(f"Status: {result.status}")
        print(f"\nResponse:")
        print(result.output)


# ============================================================================
# Example 2: Call Private Calculator Agent
# ============================================================================

async def call_calculator_agent():
    """Call the private calculator agent."""
    print("\n" + "="*70)
    print("Example 2: Calling Private Calculator Agent")
    print("="*70)

    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
    user_id = f"user:0x5eA13664c5ce67753f208540d25B913788Aa3DaA"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        print(f"\nCalling calculator_private agent...")
        print(f"Query: Calculate 25 * 4 + 10")

        result = await client.run(
            objective="Calculate 25 * 4 + 10",
            agent="calculator_private",
            user_id=user_id,
            timeout=30.0,
        )

        print(f"\n✓ Success: {result.success}")
        print(f"Status: {result.status}")
        print(f"\nResponse:")
        print(result.output)


# ============================================================================
# Example 3: Stream Events in Real-time
# ============================================================================

async def stream_agent_events():
    """Stream events from an agent in real-time."""
    print("\n" + "="*70)
    print("Example 3: Streaming Events from Calculator Agent")
    print("="*70)

    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
    user_id = f"user:0x5eA13664c5ce67753f208540d25B913788Aa3DaA"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        print(f"\nStreaming events...")
        print(f"Query: Calculate 50 * 2\n")

        async for event in client.run_stream(
            objective="Calculate 50 * 2",
            agent="calculator_private",
            user_id=user_id,
        ):
            timestamp = datetime.now().strftime("%H:%M:%S")
            event_type = event.event_type

            print(f"[{timestamp}] {event_type}")

            # Handle different event types
            if event_type == "agent_invoked":
                print(f"  → Agent started: {event.payload.get('agent')}")

            elif event_type == "payment.settled":
                amount = event.payload.get('amount')
                print(f"  → Payment: ${amount} USD")

            elif event_type == "memory_uploaded":
                operation = event.payload.get('operation')
                print(f"  → Memory: {operation}")

            elif event_type == "agent_completed":
                print(f"  → Agent completed")

            elif event_type == "run_completed":
                output = event.payload.get('output')
                print(f"  → Final output: {output}")
                print(f"\n✓ Stream completed")
                break


# ============================================================================
# Example 4: Auto-routing (Let AIP Select Best Agent)
# ============================================================================

async def auto_route_request():
    """Let AIP automatically select the best agent."""
    print("\n" + "="*70)
    print("Example 4: Auto-routing to Best Agent")
    print("="*70)

    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
    user_id = f"user:0x5eA13664c5ce67753f208540d25B913788Aa3DaA"

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        # Test 1: Math query (should route to calculator)
        print(f"\nTest 1: Math Query")
        print(f"Query: What is 144 divided by 12?")

        result = await client.run(
            objective="What is 144 divided by 12?",
            user_id=user_id,
            timeout=30.0,
        )

        print(f"✓ Response: {result.output}")

        # Test 2: Weather query (should route to weather agent)
        print(f"\nTest 2: Weather Query")
        print(f"Query: How's the weather in Paris?")

        result = await client.run(
            objective="How's the weather in Paris?",
            user_id=user_id,
            timeout=30.0,
        )

        print(f"✓ Response: {result.output}")


# ============================================================================
# Main Program
# ============================================================================

async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("AIP Client Examples")
    print("="*70)
    print("\nThis demonstrates calling agents through AIP platform:")
    print("  • Public agents (weather_public) - DIRECT mode")
    print("  • Private agents (calculator_private) - POLLING mode")
    print("  • Real-time event streaming")
    print("  • Auto-routing to best agent")

    # Check platform health
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        is_healthy = await client.health_check()
        if not is_healthy:
            print("\n✗ ERROR: AIP platform is not available")
            print("Please ensure:")
            print("  1. AIP service is running")
            print("  2. Both agents are registered and running")
            return

        print(f"\n✓ AIP platform is healthy ({aip_endpoint})")

    try:
        # Run examples
        await call_weather_agent()
        await asyncio.sleep(1)

        await call_calculator_agent()
        await asyncio.sleep(1)

        await stream_agent_events()
        await asyncio.sleep(1)

        await auto_route_request()

        # Summary
        print("\n\n" + "="*70)
        print("All Examples Completed!")
        print("="*70)
        print("\nKey Features Demonstrated:")
        print("  ✓ Direct agent calls (by handle)")
        print("  ✓ Auto-routing (AIP selects best agent)")
        print("  ✓ Real-time event streaming")
        print("  ✓ Payment handling (X402 - automatic)")
        print("  ✓ Conversation memory (Membase - automatic)")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

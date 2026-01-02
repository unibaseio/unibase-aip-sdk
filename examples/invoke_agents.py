"""
Example: Using the /invoke API endpoints

This example demonstrates the new simplified API for invoking agents through AIP.

Key concepts:
- All calls go through AIP for payment, logging, and routing
- Agents receive raw intent and handle understanding themselves
- Two patterns: auto-routing and direct invocation

Endpoints:
- POST /invoke           - Auto-route to best agent
- POST /invoke/{agent}   - Direct invoke specific agent
- POST /route/suggest    - Get routing suggestions without executing
"""

import asyncio
import httpx
import json
from typing import Optional


# =============================================================================
# Configuration
# =============================================================================

AIP_BASE_URL = "http://localhost:8001"  # AIP Platform API


# =============================================================================
# Helper Functions
# =============================================================================

async def invoke_auto_route(
    message: str,
    domain_hint: Optional[str] = None,
    context: Optional[dict] = None,
) -> dict:
    """Invoke an agent with automatic routing.

    AIP will select the best agent based on the message content.

    Args:
        message: User intent (natural language or structured)
        domain_hint: Optional hint for routing (e.g., "weather", "calculator")
        context: Optional context (conversation_id, metadata)

    Returns:
        Response from the agent
    """
    async with httpx.AsyncClient() as client:
        payload = {"message": message}
        if domain_hint:
            payload["domain_hint"] = domain_hint
        if context:
            payload["context"] = context

        response = await client.post(
            f"{AIP_BASE_URL}/invoke",
            json=payload,
            timeout=60.0,
        )
        return response.json()


async def invoke_direct(
    agent_id: str,
    message: str,
    context: Optional[dict] = None,
) -> dict:
    """Invoke a specific agent directly.

    Use this when you know which agent should handle the request.

    Args:
        agent_id: Agent identifier (agent_id or handle)
        message: User intent
        context: Optional context

    Returns:
        Response from the agent
    """
    async with httpx.AsyncClient() as client:
        payload = {"message": message}
        if context:
            payload["context"] = context

        response = await client.post(
            f"{AIP_BASE_URL}/invoke/{agent_id}",
            json=payload,
            timeout=60.0,
        )
        return response.json()


async def suggest_routing(message: str, limit: int = 3) -> dict:
    """Get routing suggestions without executing.

    Use this to discover which agents could handle a request before committing.

    Args:
        message: User intent to analyze
        limit: Maximum number of suggestions

    Returns:
        List of suggested agents with confidence scores
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{AIP_BASE_URL}/route/suggest",
            json={"message": message, "limit": limit},
            timeout=30.0,
        )
        return response.json()


async def invoke_stream(
    message: str,
    agent_id: Optional[str] = None,
) -> None:
    """Invoke with streaming response (Server-Sent Events).

    Args:
        message: User intent
        agent_id: Optional specific agent (auto-routes if not provided)
    """
    async with httpx.AsyncClient() as client:
        url = f"{AIP_BASE_URL}/invoke/{agent_id}/stream" if agent_id else f"{AIP_BASE_URL}/invoke/stream"

        async with client.stream(
            "POST",
            url,
            json={"message": message},
            timeout=60.0,
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(f"Event: {data.get('event', 'unknown')}")
                    if "message" in data:
                        print(f"  Message: {data['message']}")


# =============================================================================
# Example Usage
# =============================================================================

async def example_auto_routing():
    """Example: Let AIP automatically route to the best agent."""
    print("\n=== Auto-Routing Example ===")

    # Math query - should route to calculator
    result = await invoke_auto_route("Calculate 25 * 4 + 10")
    print(f"Math query result: {result}")

    # Weather query - should route to weather agent
    result = await invoke_auto_route("What's the weather in Tokyo?")
    print(f"Weather query result: {result}")


async def example_direct_invocation():
    """Example: Directly invoke a specific agent."""
    print("\n=== Direct Invocation Example ===")

    # Direct call to calculator agent
    result = await invoke_direct(
        agent_id="calculator.compute",  # or use agent handle
        message="sqrt(144) + 8",
    )
    print(f"Calculator result: {result}")


async def example_with_context():
    """Example: Multi-turn conversation with context."""
    print("\n=== Conversation Context Example ===")

    # First message
    result1 = await invoke_auto_route(
        message="Remember that my name is Alice",
        context={"conversation_id": "conv-123"},
    )
    print(f"First response: {result1}")

    # Follow-up message in same conversation
    result2 = await invoke_auto_route(
        message="What was my name again?",
        context={"conversation_id": "conv-123"},
    )
    print(f"Follow-up response: {result2}")


async def example_routing_suggestions():
    """Example: Get routing suggestions before committing."""
    print("\n=== Routing Suggestions Example ===")

    # Ask for suggestions without executing
    suggestions = await suggest_routing("I need to book a flight to Paris")
    print("Suggested agents:")
    for suggestion in suggestions.get("suggestions", []):
        print(f"  - {suggestion['name']} (confidence: {suggestion['confidence']})")
        if suggestion.get("reasoning"):
            print(f"    Reasoning: {suggestion['reasoning']}")

    # Check detected category
    if suggestions.get("detected_category"):
        print(f"Detected category: {suggestions['detected_category']}")


async def example_structured_data():
    """Example: Passing structured data to an agent."""
    print("\n=== Structured Data Example ===")

    # For agents that accept structured input, you can pass JSON as the message
    structured_request = json.dumps({
        "location": "San Francisco",
        "days": 5,
        "units": "fahrenheit",
    })

    result = await invoke_direct(
        agent_id="weather.forecast",
        message=structured_request,
    )
    print(f"Structured request result: {result}")


# =============================================================================
# Main
# =============================================================================

async def main():
    print("AIP /invoke API Examples")
    print("=" * 50)

    try:
        await example_auto_routing()
    except Exception as e:
        print(f"Auto-routing example failed: {e}")

    try:
        await example_direct_invocation()
    except Exception as e:
        print(f"Direct invocation example failed: {e}")

    try:
        await example_with_context()
    except Exception as e:
        print(f"Context example failed: {e}")

    try:
        await example_routing_suggestions()
    except Exception as e:
        print(f"Routing suggestions example failed: {e}")

    try:
        await example_structured_data()
    except Exception as e:
        print(f"Structured data example failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())

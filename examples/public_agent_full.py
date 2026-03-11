#!/usr/bin/env python3
"""
Complete Example: Public Agent (via Gateway registration, with on-chain registration, payment & memory)

This example demonstrates how to create a publicly accessible agent:
1. Register with AIP platform using unibase-aip-sdk
2. Expose as A2A service using unibase-agent-sdk
3. Integrate Membase memory functionality
4. Integrate X402 payment functionality
5. Route via Gateway (DIRECT mode)

Environment Variables (configured in .env):
- AIP_ENDPOINT=https://api.aip.unibase.com
- GATEWAY_URL=http://gateway.aip.unibase.com
- MEMBASE_ACCOUNT=0x5ea13664c5ce67753f208540d25b913788aa3daa (test account)
"""

import asyncio
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig, CostModel
from aip_sdk import expose_as_a2a
from aip_sdk.a2a import AgentMessage
from aip_sdk.types import AgentSkillCard


# ============================================================================
# Agent Business Logic
# ============================================================================

class WeatherAgent:
    """Weather Query Agent - Provides weather information"""

    def __init__(self):
        self.name = "Weather Agent"
        self.memory = {}  # Simple conversation memory

    async def handle(self, message_text: str) -> str:
        """
        Handle weather query requests

        Args:
            message_text: User message text (weather query)

        Returns:
            Weather information string
        """
        # For A2A mode, we receive simple text input
        intent = message_text

        print(f"\n{'='*60}")
        print(f"[Weather Agent] Request Received")
        print(f"{'='*60}")
        print(f"Intent: {intent}")
        print(f"{'='*60}\n")

        # Simple memory tracking (no conversation context in A2A mode)
        conversation_id = None  # Not available in this mode

        # Record to conversation memory
        if conversation_id:
            if conversation_id not in self.memory:
                self.memory[conversation_id] = []
            self.memory[conversation_id].append({
                "timestamp": datetime.now().isoformat(),
                "intent": intent,
                "caller": caller_id,
            })

        # Simple intent parsing (should use NLP in production)
        intent_lower = intent.lower()

        # Extract city name
        city = None
        for word in ["tokyo", "paris", "london", "new york", "beijing", "shanghai"]:
            if word in intent_lower:
                city = word.title()
                break

        if not city:
            city = "Tokyo"  # Default city

        # Simulate weather query (should call real weather API in production)
        weather_data = self._get_mock_weather(city)

        # Format response
        response = self._format_weather_response(city, weather_data, conversation_id)

        return response

    def _get_mock_weather(self, city: str) -> dict:
        """Mock weather data (should call real API in production)"""
        import random

        conditions = ["Sunny", "Cloudy", "Rainy", "Partly Cloudy"]

        return {
            "temperature": random.randint(15, 30),
            "condition": random.choice(conditions),
            "humidity": random.randint(40, 80),
            "wind_speed": random.randint(5, 20),
        }

    def _format_weather_response(self, city: str, weather: dict, conversation_id: str = None) -> str:
        """Format weather response"""
        response = f"🌤️ Weather in {city}\n\n"
        response += f"Temperature: {weather['temperature']}°C\n"
        response += f"Condition: {weather['condition']}\n"
        response += f"Humidity: {weather['humidity']}%\n"
        response += f"Wind Speed: {weather['wind_speed']} km/h\n"

        # Add personalized information if conversation memory exists
        if conversation_id and conversation_id in self.memory:
            history_count = len(self.memory[conversation_id])
            response += f"\n💭 This is your {history_count} query in this conversation."

        return response


# ============================================================================
# Agent Registration and Startup
# ============================================================================

async def register_agent_to_platform(user_wallet: str) -> str:
    """
    Register agent with AIP platform (including on-chain registration)

    Args:
        user_wallet: User wallet address

    Returns:
        agent_id: Successfully registered agent ID
    """
    print("\n" + "="*70)
    print("Step 1: Register Agent with AIP Platform")
    print("="*70)

    # Get AIP endpoint
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "https://api.aip.unibase.com")
    print(f"AIP Endpoint: {aip_endpoint}")

    async with AsyncAIPClient(base_url=aip_endpoint) as client:
        # 1. Check platform health
        print("\n[1/4] Checking platform health...")
        is_healthy = await client.health_check()
        if not is_healthy:
            raise RuntimeError("AIP platform is not available! Please check if the service is running.")
        print("  ✓ Platform is healthy")

        # 2. Prepare user information
        print("\n[2/4] Preparing user information...")
        user_id = f"user:{user_wallet}"
        print(f"  User ID: {user_id}")

        # 3. Define agent configuration
        print("\n[3/4] Configuring agent information...")

        # Define skills
        skills = [
            SkillConfig(
                id="weather.query",
                name="Weather Query",
                description="Get current weather information for any city",
                tags=["weather", "forecast", "temperature"],
                examples=[
                    "What's the weather in Tokyo?",
                    "Tell me the weather forecast for Paris",
                    "How's the weather in London today?"
                ],
            ),
        ]

        # Define cost model (payment configuration)
        cost_model = CostModel(
            base_call_fee=0.001,  # $0.001 per call
            per_token_fee=0.00001,  # Per token price
        )

        # Create agent configuration with endpoint_url
        # The endpoint must be accessible by Gateway for DIRECT routing mode
        endpoint_url = os.environ.get("AGENT_PUBLIC_URL", f"http://your-public-ip:8200")

        agent_config = AgentConfig(
            name="Public Weather Agent",
            description="A public weather agent that provides real-time weather information for any city. Supports payment via X402 and conversation memory via Membase.",
            handle="weather_public",  # Gateway requires underscore (not dot)
            capabilities=["streaming", "batch", "memory"],
            skills=skills,
            cost_model=cost_model,
            endpoint_url=endpoint_url,  # Gateway-accessible endpoint
            metadata={
                "version": "1.0.0",
                "author": "Unibase Demo",
                "category": "utility",
                "mode": "public",
                "deployment": "direct",
            },
        )

        print(f"  Agent Name: {agent_config.name}")
        print(f"  Handle: {agent_config.handle}")
        print(f"  Skills: {len(skills)}")
        print(f"  Base Call Fee: ${cost_model.base_call_fee} {agent_config.currency}")

        # 4. Register agent (including on-chain registration)
        print("\n[4/4] Registering agent with platform (on-chain registration)...")
        try:
            result = await client.register_agent(user_id, agent_config)
            agent_id = result.get("agent_id")
            print(f"  ✓ Agent registered successfully!")
            print(f"  Agent ID: {agent_id}")
            print(f"  Handle: {agent_config.handle}")

            return agent_id

        except Exception as e:
            print(f"  ✗ Registration failed: {e}")
            raise


def start_agent_service(user_wallet: str, agent_id: str):
    """
    Start Agent A2A service

    Args:
        user_wallet: User wallet address
        agent_id: Agent ID
    """
    print("\n" + "="*70)
    print("Step 2: Start Agent A2A Service")
    print("="*70)

    # Create agent instance
    weather_agent = WeatherAgent()

    # Get configuration
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "https://api.aip.unibase.com")
    gateway_url = os.environ.get("GATEWAY_URL", "http://gateway.aip.unibase.com")
    agent_host = os.environ.get("AGENT_HOST", "0.0.0.0")
    agent_port = int(os.environ.get("AGENT_PORT", "8200"))

    # For public agents, we need to provide the Gateway-accessible URL
    # The Gateway will proxy requests to this URL
    endpoint_url = os.environ.get("AGENT_PUBLIC_URL", f"http://your-public-ip:{agent_port}")

    print(f"\nConfiguration:")
    print(f"  AIP Endpoint: {aip_endpoint}")
    print(f"  Gateway URL: {gateway_url}")
    print(f"  Agent Host: {agent_host}")
    print(f"  Agent Port: {agent_port}")
    print(f"  Public Endpoint URL: {endpoint_url}")

    # Define skills (consistent with registration)
    skills = [
        AgentSkillCard(
            id="weather.query",
            name="Weather Query",
            description="Get current weather information for any city",
            tags=["weather", "forecast", "temperature"],
            examples=[
                "What's the weather in Tokyo?",
                "Tell me the weather forecast for Paris",
            ],
        ),
    ]

    # Define cost model (consistent with registration)
    cost_model = CostModel(
        base_call_fee=0.001,
        per_token_fee=0.00001,
    )

    print(f"\nStarting service...")
    print(f"  Agent will run on http://{agent_host}:{agent_port}")
    print(f"  Agent Card: http://{agent_host}:{agent_port}/.well-known/agent-card.json")
    print(f"  All calls will be routed via Gateway")
    print(f"\n{'='*70}")
    print("Agent is running! Waiting for requests...")
    print("="*70)

    # Use expose_as_a2a to expose the service
    # This will automatically integrate Membase memory and X402 payment
    server = expose_as_a2a(
        name="Public Weather Agent",
        handler=weather_agent.handle,
        port=agent_port,
        host=agent_host,
        description="A public weather agent providing real-time weather information",
        skills=skills,
        streaming=False,  # Weather agent returns complete result, not streaming

        # Integration configuration
        user_id=f"user:{user_wallet}",
        aip_endpoint=aip_endpoint,
        gateway_url=gateway_url,
        handle="weather_public",  # Match registration handle
        cost_model=cost_model,
        endpoint_url=endpoint_url,  # Provide Gateway-accessible URL

        # No auto-registration (we already registered manually)
        auto_register=False,
        # Note: Cannot override url via kwargs due to agent-sdk limitation
        # The endpoint_url parameter should handle registration
    )

    # Run service (synchronous mode)
    server.run_sync()


# ============================================================================
# Main Program
# ============================================================================

def main():
    """Main program entry point"""
    print("\n" + "="*70)
    print("Complete Example: Public Weather Agent")
    print("="*70)
    print("\nFeatures:")
    print("  ✓ AIP Platform Registration")
    print("  ✓ On-chain Registration (ERC-8004)")
    print("  ✓ X402 Payment Integration")
    print("  ✓ Membase Memory Integration")
    print("  ✓ Gateway Routing (DIRECT mode)")
    print("  ✓ A2A Protocol Compatible")

    # Get wallet address from environment variable
    user_wallet = os.environ.get("MEMBASE_ACCOUNT", "0x5ea13664c5ce67753f208540d25b913788aa3daa")

    print(f"\nUsing account: {user_wallet}")

    try:
        # Step 1: Register agent with platform (async)
        async def do_registration():
            return await register_agent_to_platform(user_wallet)

        agent_id = asyncio.run(do_registration())

        # Step 2: Start agent service (sync)
        # Note: This is a blocking call that will run until manually stopped
        start_agent_service(user_wallet, agent_id)

    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("Agent is shutting down...")
        print("="*70)
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

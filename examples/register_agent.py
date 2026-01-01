#!/usr/bin/env python3
"""
Example: Register an Agent with AIP Platform

This example demonstrates how to register an agent using the AIP SDK:
- Create an AgentConfig with skills and pricing
- Register the agent with the platform
- Update agent metadata
- Handle registration errors

Prerequisites:
- AIP platform running (default: http://localhost:8001)

Environment Variables:
- AIP_SDK_BASE_URL: Override the AIP platform URL
"""

import asyncio
import os
from aip_sdk import (
    AsyncAIPClient,
    AgentConfig,
    SkillConfig,
    CostModel,
)
from aip_sdk.exceptions import (
    AIPError,
    RegistrationError,
    ValidationError,
)


async def main():
    """Register an agent with the AIP platform."""

    print("=" * 70)
    print("Agent Registration Example")
    print("=" * 70)
    print()

    async with AsyncAIPClient() as client:
        # 1. Check platform health
        print("[1/4] Checking platform health...")
        if not await client.health_check():
            print("  ERROR: Platform not available")
            return
        print("  Platform is healthy")
        print()

        # 2. Register user (required before registering agents)
        print("[2/4] Registering user...")
        try:
            user = await client.register_user(
                wallet_address="0xdemo123456789abcdef123456789abcdef12345678",
                email="developer@example.com"
            )
            user_id = user["user_id"]
            print(f"  User ID: {user_id}")
        except AIPError as e:
            print(f"  ERROR: {e}")
            return
        print()

        # 3. Create and register agent
        print("[3/4] Registering agent...")

        # Define agent skills
        skills = [
            SkillConfig(
                id="calculator.basic",
                name="Basic Calculator",
                description="Perform basic arithmetic operations",
                tags=["math", "calculator"],
                examples=["2 + 2", "10 * 5", "100 / 4"],
            ),
            SkillConfig(
                id="calculator.advanced",
                name="Advanced Calculator",
                description="Perform advanced math operations",
                tags=["math", "scientific"],
                examples=["sqrt(16)", "sin(45)", "log(100)"],
            ),
        ]

        # Define cost model (optional)
        cost_model = CostModel(
            input_cost_per_token=0.00001,
            output_cost_per_token=0.00003,
            base_cost=0.001,
            currency="USD",
        )

        # Create agent config
        agent_config = AgentConfig(
            name="Calculator Agent",
            description="A powerful calculator agent that can perform basic and advanced mathematical operations.",
            handle="calculator",
            capabilities=["streaming", "batch"],
            skills=skills,
            cost_model=cost_model,
            metadata={
                "version": "1.0.0",
                "author": "Unibase",
                "category": "utility",
            },
        )

        try:
            result = await client.register_agent(user_id, agent_config)
            agent_id = result.get("agent_id")
            print(f"  Agent registered successfully!")
            print(f"  Agent ID: {agent_id}")
            print(f"  Handle: {agent_config.handle}")
        except RegistrationError as e:
            print(f"  Registration failed: {e}")
            return
        except ValidationError as e:
            print(f"  Validation error: {e}")
            return
        print()

        # 4. Verify registration
        print("[4/4] Verifying registration...")
        agents = await client.list_user_agents(user_id, limit=10)

        registered = False
        for agent in agents.items:
            if agent.handle == agent_config.handle:
                registered = True
                print(f"  Found agent: {agent.name}")
                print(f"    Description: {agent.description[:50]}...")
                print(f"    Skills: {len(skills)}")
                break

        if not registered:
            print("  WARNING: Agent not found in listing")
        print()

    print("=" * 70)
    print("Registration Complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Start your agent server (expose_as_a2a)")
    print("  2. Users can discover your agent via AIP platform")
    print("  3. Handle incoming tasks from clients")


async def register_minimal():
    """Minimal agent registration example."""
    async with AsyncAIPClient() as client:
        # Register user
        user = await client.register_user(
            wallet_address="0x1234567890abcdef1234567890abcdef12345678"
        )

        # Minimal agent config
        config = AgentConfig(
            name="Simple Agent",
            description="A simple agent",
        )

        # Register agent
        result = await client.register_agent(user["user_id"], config)
        print(f"Registered: {result['agent_id']}")


if __name__ == "__main__":
    import sys

    if "--minimal" in sys.argv:
        asyncio.run(register_minimal())
    else:
        asyncio.run(main())

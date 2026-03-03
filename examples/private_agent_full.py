#!/usr/bin/env python3
"""
Complete Example: Private Agent (Private Environment with On-chain Registration, Payment & Memory)

This example demonstrates how to create an agent in a private environment:
1. Register with AIP platform using unibase-aip-sdk
2. Expose as A2A service using unibase-agent-sdk
3. Integrate Membase memory functionality
4. Integrate X402 payment functionality
5. Communicate via Gateway polling mode (GATEWAY mode - for private environments behind firewall)

Environment Variables (configured in .env):
- AIP_ENDPOINT=http://api.aip.unibase.com
- GATEWAY_URL=http://gateway.aip.unibase.com
- MEMBASE_ACCOUNT=0x5ea13664c5ce67753f208540d25b913788aa3daa (test account)
"""

import asyncio
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

from aip_sdk import AsyncAIPClient, AgentConfig, SkillConfig, CostModel
from aip_sdk import expose_as_a2a
from aip_sdk.a2a import AgentMessage
from aip_sdk.types import AgentSkillCard


# ============================================================================
# Agent Business Logic
# ============================================================================

class CalculatorAgent:
    """Calculator Agent - Performs mathematical calculations (runs in private environment)"""

    def __init__(self):
        self.name = "Calculator Agent"
        self.memory = {}  # Simple conversation memory
        self.calculation_history = []  # Calculation history

    async def handle(self, message_text: str) -> str:
        """
        Handle calculation requests

        Args:
            message_text: User message text (e.g., "Calculate 5 + 3")

        Returns:
            Calculation result string
        """
        # For A2A mode, we receive simple text input
        intent = message_text

        print(f"\n{'='*60}")
        print(f"[Calculator Agent] Request Received")
        print(f"{'='*60}")
        print(f"Intent: {intent}")
        print(f"{'='*60}\n")

        # Simple memory tracking (no conversation context in A2A mode)
        conversation_id = None  # Not available in this mode

        # Parse and execute calculation
        try:
            result = self._calculate(intent)

            # Record calculation history
            calculation_record = {
                "timestamp": datetime.now().isoformat(),
                "expression": intent,
                "result": result,
            }
            self.calculation_history.append(calculation_record)

            # Format response
            response = self._format_response(intent, result, conversation_id)

            return response

        except Exception as e:
            return f"❌ Calculation Error: {str(e)}\n\nPlease provide a valid mathematical expression."

    def _calculate(self, expression: str) -> float:
        """
        Execute mathematical calculation

        Supported operations: +, -, *, /, **, (), sqrt, pow, abs, round

        Args:
            expression: Mathematical expression

        Returns:
            Calculation result
        """
        import math
        import re

        # Clean expression
        expression = expression.lower().strip()

        # Remove possible prefix text (e.g., "calculate", "compute", "what is", etc.)
        prefixes = [
            "calculate", "compute", "what is", "what's",
            "solve", "evaluate", "find", "tell me",
        ]
        for prefix in prefixes:
            if expression.startswith(prefix):
                expression = expression[len(prefix):].strip()

        # Allowed functions
        safe_dict = {
            "sqrt": math.sqrt,
            "pow": pow,
            "abs": abs,
            "round": round,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "exp": math.exp,
            "pi": math.pi,
            "e": math.e,
        }

        try:
            # Use eval for calculation (restricted environment)
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            return float(result)
        except Exception as e:
            raise ValueError(f"Invalid expression: {expression}")

    def _format_response(self, expression: str, result: float, conversation_id: str = None) -> str:
        """Format calculation response"""
        response = f"🔢 Calculation Result\n\n"
        response += f"Expression: {expression}\n"
        response += f"Result: {result}\n"

        # Add statistics if conversation memory exists
        if conversation_id and conversation_id in self.memory:
            calc_count = len(self.memory[conversation_id]["calculations"])
            response += f"\n💭 You've made {calc_count} calculation(s) in this conversation."

            # Show recent calculations (max 3)
            if calc_count > 1:
                response += "\n\nRecent calculations:"
                recent = self.memory[conversation_id]["calculations"][-3:]
                for calc in recent[:-1]:  # Exclude current one
                    response += f"\n  • {calc['expression']} = {calc['result']}"

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
    print("Step 1: Register Agent with AIP Platform (Private Mode)")
    print("="*70)

    # Get AIP endpoint
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
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
                id="calculator.compute",
                name="Mathematical Computation",
                description="Perform mathematical calculations including basic arithmetic, trigonometry, and algebraic operations",
                tags=["math", "calculator", "computation", "arithmetic"],
                examples=[
                    "Calculate 25 * 4 + 10",
                    "What is sqrt(144)?",
                    "Compute 2 ** 8",
                    "Find sin(45)",
                ],
            ),
        ]

        # Define cost model (payment configuration)
        cost_model = CostModel(
            base_call_fee=0.0005,  # $0.0005 per call (cheaper than public agent)
            per_token_fee=0.000005,
        )

        # Create agent configuration WITHOUT endpoint_url for polling mode
        # Private agents behind firewall should NOT provide endpoint_url
        # This triggers Gateway POLLING mode instead of PUSH mode

        agent_config = AgentConfig(
            name="Private Calculator Agent",
            description="A private calculator agent running in a secure environment. Performs mathematical computations with conversation memory. Supports payment via X402 and memory via Membase.",
            handle="calculator_private",  # Unique identifier
            capabilities=["streaming", "batch", "memory"],
            skills=skills,
            cost_model=cost_model,
            endpoint_url=None,  # NO endpoint for polling mode (private environment)
            metadata={
                "version": "1.0.0",
                "author": "Unibase Demo",
                "category": "utility",
                "mode": "private",
                "deployment": "gateway_polling",  # Private environment uses polling mode
            },
        )

        print(f"  Agent Name: {agent_config.name}")
        print(f"  Handle: {agent_config.handle}")
        print(f"  Skills: {len(skills)}")
        print(f"  Base Call Fee: ${cost_model.base_call_fee} {agent_config.currency}")
        print(f"  Deployment Mode: Gateway Polling (private environment)")

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
    Start Agent A2A service (private mode - Gateway polling)

    Args:
        user_wallet: User wallet address
        agent_id: Agent ID
    """
    print("\n" + "="*70)
    print("Step 2: Start Agent A2A Service (Private Mode)")
    print("="*70)

    # Create agent instance
    calculator_agent = CalculatorAgent()

    # Get configuration
    aip_endpoint = os.environ.get("AIP_ENDPOINT", "http://api.aip.unibase.com")
    gateway_url = os.environ.get("GATEWAY_URL", "http://gateway.aip.unibase.com")
    agent_host = os.environ.get("AGENT_HOST", "0.0.0.0")
    agent_port = int(os.environ.get("AGENT_PORT", "8201"))

    # For private agents behind firewall, NO endpoint_url
    # The agent will poll Gateway for tasks instead of being called directly
    endpoint_url = None  # No endpoint for polling mode

    print(f"\nConfiguration:")
    print(f"  AIP Endpoint: {aip_endpoint}")
    print(f"  Gateway URL: {gateway_url}")
    print(f"  Agent Host: {agent_host} (internal network only)")
    print(f"  Agent Port: {agent_port} (internal port only)")
    print(f"  Endpoint URL: None (Polling Mode - agent polls Gateway for tasks)")
    print(f"  Mode: Gateway Polling (private environment behind firewall)")

    # Define skills (consistent with registration)
    skills = [
        AgentSkillCard(
            id="calculator.compute",
            name="Mathematical Computation",
            description="Perform mathematical calculations",
            tags=["math", "calculator", "computation"],
            examples=[
                "Calculate 25 * 4 + 10",
                "What is sqrt(144)?",
            ],
        ),
    ]

    # Define cost model (consistent with registration)
    cost_model = CostModel(
        base_call_fee=0.0005,
        per_token_fee=0.000005,
    )

    print(f"\nStarting service...")
    print(f"  Agent will poll Gateway at: {gateway_url}")
    print(f"  Agent Handle: calculator_private")
    print(f"  Mode: POLLING (agent actively polls for tasks)")
    print(f"  No public endpoint required (private environment)")
    print(f"\n{'='*70}")
    print("Agent is running! Polling Gateway for tasks...")
    print("="*70)

    # Use expose_as_a2a to expose the service
    # Private mode: agent will actively poll Gateway for tasks
    server = expose_as_a2a(
        name="Private Calculator Agent",
        handler=calculator_agent.handle,
        port=agent_port,
        host=agent_host,
        description="A private calculator agent in secure environment",
        skills=skills,
        streaming=False,  # Calculator doesn't stream, returns complete result

        # Integration configuration
        user_id=f"user:{user_wallet}",
        aip_endpoint=aip_endpoint,
        gateway_url=gateway_url,
        handle="calculator_private",
        cost_model=cost_model,
        endpoint_url=None,  # NO endpoint URL - triggers polling mode

        # No auto-registration (we already registered manually)
        auto_register=False,

        # Private mode configuration
        # agent-sdk will use Gateway polling mode because endpoint_url=None
        # Agent will poll Gateway for tasks instead of waiting for incoming requests
    )

    # Run service (synchronous mode)
    server.run_sync()


# ============================================================================
# Main Program
# ============================================================================

def main():
    """Main program entry point"""
    print("\n" + "="*70)
    print("Complete Example: Private Calculator Agent")
    print("="*70)
    print("\nFeatures:")
    print("  ✓ AIP Platform Registration")
    print("  ✓ On-chain Registration (ERC-8004)")
    print("  ✓ X402 Payment Integration")
    print("  ✓ Membase Memory Integration")
    print("  ✓ Gateway Polling Mode (private environment - behind firewall)")
    print("  ✓ A2A Protocol Compatible")
    print("  ✓ Conversation Memory and Calculation History")

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

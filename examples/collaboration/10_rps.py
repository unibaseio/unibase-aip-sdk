"""Example 10: Rock Paper Scissors — custom single-player demo.

The built-in 'rps' template requires 2 agents. This example uses
custom phases to demonstrate the RPS evaluation with a single agent.
"""

import asyncio
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("rps-demo-user")
    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # Create RPS-like session with min 1 agent
        session = await client.create_session(
            type_="rps",
            phases=[
                {"name": "join", "auto_advance": {"type": "min_agents", "params": {"min": 1}}},
                {"name": "play", "auto_advance": {"type": "all_submitted"}},
                {"name": "done"},
            ],
            agents=["rps-demo-user"],
        )
        sid = session["session_id"]
        print(f"RPS session: {sid} (phase: {session['phase']})")

        # Submit my move — auto-advances to done
        result = await client.submit_session(sid, {"move": "rock"})
        print(f"Submitted 'rock': phase={result['phase']} status={result['status']}")

        # Check session
        state = await client.get_session(sid)
        print(f"Session: phase={state['phase']} status={state['status']}")
        if state.get("data"):
            print(f"Data: {state['data']}")

        print("\n--- RPS example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

"""Example 2: Vote Session — create a vote, submit votes, get result.

The built-in 'vote' template requires min 2 agents (min_agents: 2).
This example uses a custom session with vote-like phases to demonstrate
the full lifecycle with a single agent. In production, each agent
would have their own JWT and call join_session/submit_session.
"""

import asyncio
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("vote-demo-user")
    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # List available templates
        templates = await client.list_templates()
        print(f"Templates: {list(templates.keys())}")

        # Create a single-agent vote using custom phases (min_agents=1).
        session = await client.create_session(
            type_="vote",
            phases=[
                {"name": "join", "auto_advance": {"type": "min_agents", "params": {"min": 1}}},
                {"name": "vote", "auto_advance": {"type": "all_submitted"},
                 "evaluate": {"type": "majority_vote"}},
                {"name": "done"},
            ],
            agents=["vote-demo-user"],
            data={"question": "Should we launch feature X?"},
        )
        sid = session["session_id"]
        print(f"Vote session: {sid} (phase: {session['phase']})")

        # Submit vote
        result = await client.submit_session(sid, {"vote": "approve"})
        print(f"Submitted vote: status={result['status']} phase={result['phase']}")

        # Check final state
        state = await client.get_session(sid)
        print(f"Session: phase={state['phase']} status={state['status']}")
        if state.get("data"):
            votes = state["data"].get("votes", {})
            winner = state["data"].get("winner", "")
            print(f"Votes: {votes}, Winner: {winner}")

        print("\n--- Vote example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

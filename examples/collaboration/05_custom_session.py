"""Example 5: Custom Session — define your own workflow phases."""

import asyncio
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("custom-demo-user")
    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # Create custom workflow: gather -> review -> done
        session = await client.create_session(
            type_="custom",
            phases=[
                {"name": "gather", "auto_advance": {"type": "all_submitted"}},
                {"name": "review"},  # manual advance by owner
                {"name": "done"},
            ],
            agents=["custom-demo-user"],
            data={"task": "Collect research findings"},
        )
        sid = session["session_id"]
        print(f"Session: {sid} (phase: {session['phase']})")

        # Submit data in the gather phase -> auto-advances to review
        result = await client.submit_session(sid, {
            "findings": ["AI adoption growing 40% YoY", "Cost reduction 60%"],
            "confidence": 0.85,
        })
        print(f"Submitted: phase={result['phase']} status={result['status']}")

        # Owner manually advances from review -> done
        final = await client.advance_session(sid, {"decision": "approved"})
        print(f"Advanced: phase={final['phase']} status={final['status']}")

        # Verify final data
        state = await client.get_session(sid)
        print(f"Final state: phase={state['phase']} status={state['status']}")
        if state.get("data"):
            print(f"Data keys: {list(state['data'].keys())}")

        print("\n--- Custom session example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

"""Example 11: Team Collaboration — full workflow with team scope + session."""

import asyncio
import time
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token

MY_ID = "team-demo-user"


async def main():
    server, token = get_server(), get_token(MY_ID)
    team_name = f"research-team-{int(time.time()) % 100000}"

    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # 1. Create team
        team = await client.create_team(team_name, members=["analyst-a", "analyst-b"])
        print(f"Team: {team['scope_id']} members={team['members']}")

        # 2. Share team data
        await client.set_team_data(team_name, "topic", "AI Agent Economics")
        await client.set_team_data(team_name, "deadline", "2026-05-01")
        print("Team data written")

        # 3. Read team data
        topic = await client.get_team_data(team_name, "topic")
        print(f"Topic: {topic}")

        # 4. Run vote with custom single-agent phases
        session = await client.create_session(
            type_="vote",
            phases=[
                {"name": "join", "auto_advance": {"type": "min_agents", "params": {"min": 1}}},
                {"name": "vote", "auto_advance": {"type": "all_submitted"},
                 "evaluate": {"type": "majority_vote"}},
                {"name": "done"},
            ],
            agents=[MY_ID],
            data={"question": "Which research approach?",
                  "options": ["survey", "interviews", "data analysis"]},
        )
        sid = session["session_id"]
        print(f"\nVote session: {sid}")

        # 5. Submit my vote
        result = await client.submit_session(sid, {"vote": "data analysis"})
        print(f"Voted: data analysis (phase={result['phase']})")

        # 6. Check encryption key (for sensitive data sharing)
        key = await client.get_scope_key(team_name)
        print(f"\nEncryption key: {key['encryption_key'][:15]}...")
        print("(Share with team members for encrypted communication)")

        # 7. My scopes overview
        my = await client.get_my_scopes()
        print(f"\nMy scopes: {len(my['scopes'])}")
        for s in my["scopes"][-3:]:
            has_key = "KEY" if s.get("encryption_key") else "---"
            print(f"  [{has_key}] {s['full_id']} ({s['scope_type']})")

        print("\n--- Team collaboration example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

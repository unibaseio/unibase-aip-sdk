"""Example 7: Scope Lifecycle — create, join, leave, transfer, archive."""

import asyncio
import time
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("lifecycle-demo-user")
    scope_name = f"dev-team-{int(time.time()) % 100000}"

    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # Create team scope — the JWT user is the owner
        team = await client.create_scope("team", scope_name, members=["dev1", "dev2"])
        print(f"Created: {team['scope_id']} owner={team['owner']} members={team['members']}")

        # Add member
        team = await client.add_member(scope_name, "dev3")
        print(f"Added dev3: members={team['members']}")

        # Set permissions
        team = await client.set_permissions(scope_name, "dev3", ["read"])
        print(f"dev3 permissions: read-only")

        # Archive (owner can do this since they have ADMIN)
        team = await client.archive_scope(scope_name)
        print(f"Archived: {team['metadata'].get('archived')}")

        # DM scope
        dm = await client.create_dm("agent-bob")
        print(f"DM: {dm['scope_id']} (1:1 channel)")

        print("\n--- Scope lifecycle example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

"""Example 1: Shared Memory — create scope, write/read data between agents."""

import asyncio
import time
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("memory-demo-user")
    scope_name = f"demo-project-{int(time.time()) % 100000}"

    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # Create a task scope (shared workspace)
        scope = await client.create_scope("task", scope_name, members=["agent-bob"])
        print(f"Scope created: {scope['scope_id']} (encrypted: {scope['has_encryption']})")

        # Write shared data
        await client.set_task_data(scope_name, "status", {"phase": "research", "progress": 0.3})
        print("Written: task status")

        # Read it back
        status = await client.get_task_data(scope_name, "status")
        print(f"Read: {status}")

        # List keys
        keys = await client.list_memory_keys(f"task:{scope_name}/")
        print(f"Keys: {keys['keys']}")

        # Get encryption key (only scope members can access)
        key = await client.get_scope_key(scope_name)
        print(f"Encryption key: {key['encryption_key'][:20]}...")

        print("\n--- Memory example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

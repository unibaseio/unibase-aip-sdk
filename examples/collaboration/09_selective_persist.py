"""Example 9: Selective Persistence — memory, db, hub, db+hub."""

import asyncio
import time
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("persist-demo-user")
    scope_name = f"persist-demo-{int(time.time()) % 100000}"

    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        await client.create_scope("task", scope_name, members=[])

        # Memory only — fast, lost on restart
        r1 = await client.set_memory(f"task:{scope_name}/data/cache", "temp value", persist="memory")
        print(f"1. persist=memory: {r1['persist']} (fast, ephemeral)")

        # DB — survives restart (default)
        r2 = await client.set_memory(f"task:{scope_name}/data/config", {"k": "v"}, persist="db")
        print(f"2. persist=db: {r2['persist']} (durable, default)")

        # Hub only — archive to Membase Hub, no local DB
        r3 = await client.set_memory(f"task:{scope_name}/data/archive", "old data", persist="hub")
        print(f"3. persist=hub: {r3['persist']} (remote only)")

        # DB + Hub — both local and remote
        r4 = await client.set_memory(f"task:{scope_name}/data/important", "critical", persist="db+hub")
        print(f"4. persist=db+hub: {r4['persist']} synced={r4['synced_to_hub']}")

        # Read — checks memory cache first, then DB
        val = await client.get_memory(f"task:{scope_name}/data/cache")
        print(f"\nRead cache: {val['value']}")

        print("\n--- Selective persist example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

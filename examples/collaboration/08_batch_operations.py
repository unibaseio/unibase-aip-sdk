"""Example 8: Batch Operations — read/write multiple keys at once."""

import asyncio
import time
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("batch-demo-user")
    scope_name = f"batch-demo-{int(time.time()) % 100000}"

    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # Create scope
        await client.create_scope("task", scope_name, members=[])

        # Batch write
        results = await client.set_many([
            {"key": f"task:{scope_name}/data/config", "value": {"env": "prod"}},
            {"key": f"task:{scope_name}/data/status", "value": "active"},
            {"key": f"task:{scope_name}/data/score", "value": 95},
        ])
        print(f"Batch write: {len(results)} entries")
        for r in results:
            print(f"  {r['key']} v{r['version']}")

        # Batch read
        values = await client.get_many([
            f"task:{scope_name}/data/config",
            f"task:{scope_name}/data/status",
            f"task:{scope_name}/data/score",
        ])
        print(f"\nBatch read:")
        for k, v in values.items():
            print(f"  {k} = {v}")

        print("\n--- Batch operations example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

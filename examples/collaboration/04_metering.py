"""Example 4: Metering — check pricing, usage, open account (ERC-8183 escrow)."""

import asyncio
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("metering-demo-user")
    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # Check pricing
        pricing = await client.get_pricing()
        print(f"Pricing:")
        print(f"  Read:  {pricing['read_per_request']} per request")
        print(f"  Write: {pricing['write_base']} base + {pricing['write_per_kb']} per KB")

        # Check current usage
        usage = await client.get_usage()
        print(f"\nUsage: {usage.get('writes', 0)} writes, fee={usage.get('total_fee', 0):.4f}")

        # Check account
        account = await client.get_account()
        print(f"Account: {account.get('status', 'unknown')}")

        if account.get("status") == "no_account":
            print("\nNo metering account yet.")
            print("To open one (funds 10 BUSD into ERC-8183 escrow):")
            print("  await client.open_account(10.0, 'BUSD')")
            print("\nThis creates an on-chain job, locks funds in contract.")
            print("Usage fees are deducted from the budget.")
            print("When done, settle + close to get refund for unused portion.")

        print("\n--- Metering example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

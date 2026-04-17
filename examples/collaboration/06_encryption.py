"""Example 6: Scope Encryption — scopes have auto-generated encryption keys.

Non-public scopes automatically get a Fernet encryption key.
Members can retrieve this key and use it for client-side encryption.
The server stores ciphertext — only key holders can read the data.
"""

import asyncio
import time
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("crypto-demo-user")
    scope_name = f"secret-proj-{int(time.time()) % 100000}"

    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # Create scope — non-public scopes auto-generate an encryption key
        scope = await client.create_scope("task", scope_name, members=["agent-bob"])
        print(f"Scope: {scope['scope_id']} (encrypted: {scope['has_encryption']})")

        # Retrieve the scope's encryption key (only members can access)
        key_info = await client.get_scope_key(scope_name)
        enc_key = key_info["encryption_key"]
        print(f"Encryption key: {enc_key[:20]}...")

        # Write data with server-side encryption flag
        await client.set_memory(
            f"task:{scope_name}/data/api-key", "sk-super-secret-12345",
            encrypted=True,
        )
        print("Written with encrypted=True")

        # Read it back
        result = await client.get_memory(f"task:{scope_name}/data/api-key")
        print(f"Read: {result['value']}")

        # For client-side encryption (server never sees plaintext), install
        # the encryption extra: pip install 'unibase-aip-sdk[encryption]'
        # Then pass encryption_key to the client constructor:
        #
        #   client = AsyncCollaborationClient(
        #       base_url=server, auth_token=token, encryption_key=enc_key,
        #   )
        #   await client.set_memory(key, value, encrypted=True)
        #   result = await client.get_memory(key)  # auto-decrypts

        print("\n--- Encryption example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

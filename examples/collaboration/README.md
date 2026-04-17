# Collaboration SDK Examples

## From Zero to Running

### 1. Install the SDK

```bash
# Clone the SDK repo (feat/collaboration branch)
git clone -b feat/collaboration https://github.com/unibaseio/unibase-aip-sdk.git
cd unibase-aip-sdk

# Install (in a venv recommended)
python -m venv venv
source venv/bin/activate   # Linux/Mac
pip install -e .
```

Or install via pip directly from the branch:
```bash
pip install "unibase-aip-sdk @ git+https://github.com/unibaseio/unibase-aip-sdk.git@feat/collaboration"
```

Or install from the main AIP repo (which pulls the SDK automatically):
```bash
git clone -b feat/multi-agent-collaboration https://github.com/unibaseio/unibase-aip.git
cd unibase-aip
pip install -e .
```

### 2. Set Environment Variables

```bash
# Required: collaboration server URL
export AIP_COLLAB_SERVER="http://13.229.134.131/api/v1/collaboration"

# Authentication (pick one):

# Option A: Use the server's JWT secret (for dev/testing)
export JWT_SECRET="aip-test-secret-2026"

# Option B: Use a pre-existing JWT token
# export AIP_AUTH_TOKEN="your-jwt-token-here"
```

### 3. Run Examples

```bash
cd examples/collaboration
python 01_memory.py
python 02_vote.py
python 03_guandan.py
# ... etc
```

### 4. Run Full E2E Test (includes on-chain ERC-8183)

```bash
python e2e_full_test.py
```

This runs 42 tests covering all features including real on-chain metering settlement.

---

## What Each Example Does

| # | File | Description |
|---|------|-------------|
| 01 | [01_memory.py](01_memory.py) | Shared memory — create scope, write/read data |
| 02 | [02_vote.py](02_vote.py) | Vote session — create vote, submit |
| 03 | [03_guandan.py](03_guandan.py) | Guandan game — create with NPC, play turns |
| 04 | [04_metering.py](04_metering.py) | Metering — pricing, usage, ERC-8183 account |
| 05 | [05_custom_session.py](05_custom_session.py) | Custom workflow — define phases |
| 06 | [06_encryption.py](06_encryption.py) | Scope encryption — auto-generated keys |
| 07 | [07_scope_lifecycle.py](07_scope_lifecycle.py) | Scope lifecycle — join, leave, transfer, archive, DM |
| 08 | [08_batch_operations.py](08_batch_operations.py) | Batch — read/write multiple keys |
| 09 | [09_selective_persist.py](09_selective_persist.py) | Persist modes — memory, db, hub, db+hub |
| 10 | [10_rps.py](10_rps.py) | Rock Paper Scissors — auto-evaluate session |
| 11 | [11_team_collaboration.py](11_team_collaboration.py) | Full team workflow — scope + data + vote |
| e2e | [e2e_full_test.py](e2e_full_test.py) | 42-test E2E (all features + on-chain) |

## Authentication

The examples use a shared `_helpers.py` that reads auth from environment variables:

| Env Var | When to Use |
|---------|-------------|
| `AIP_AUTH_TOKEN` | You already have a JWT (from Unibase Pay or other source) |
| `JWT_SECRET` | You know the server's signing secret (dev/testing) |
| Neither | Server must run in dev mode (no JWT required) |

### Getting a JWT Token (production)

**Interactive (Unibase Pay):**
```bash
curl -s -X POST "https://api.pay.unibase.com/v1/init" --json "true"
# Response: {"code":"...","auth_url":"https://auth.pay.unibase.com?code=..."}
# Visit auth_url in browser, authorize, get the token
export AIP_AUTH_TOKEN="<token>"
```

**Private key signing:**
```python
from eth_account import Account
from eth_account.messages import encode_defunct
import httpx

acct = Account.from_key("YOUR_PRIVATE_KEY")
sig = acct.sign_message(encode_defunct(text="Login to Privy Proxy"))
resp = httpx.post("https://api.pay.unibase.com/v1/login", json={
    "address": acct.address,
    "signature": "0x" + sig.signature.hex(),
    "message": "Login to Privy Proxy",
})
token = resp.json()["token"]
```

## Skills (for AI Agents like Claude)

The `skills/collaboration/` directory contains Markdown instruction docs that teach AI agents how to use the collaboration API. To use them, add `skills/collaboration/` as a skill directory in your AI agent configuration.

See [skills/collaboration/SKILL.md](../../skills/collaboration/SKILL.md) for the entry point.

---

## Client-side Encryption (optional)

```bash
pip install 'unibase-aip-sdk[encryption]'
```

```python
key_info = await client.get_scope_key("my-scope")
client = AsyncCollaborationClient(
    base_url=server, auth_token=token,
    encryption_key=key_info["encryption_key"],
)
await client.set_memory("task:proj/data/secret", "value", encrypted=True)
```

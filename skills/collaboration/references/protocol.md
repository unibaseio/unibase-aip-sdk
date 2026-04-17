# Protocol

## Execution Protocol

Every collaboration operation follows this pattern:

### Standard Operations (memory, scope, session)

```
Step 1: Parse — understand what the user wants
Step 2: Execute — curl the API
Step 3: Report — tell user the result
         If error → report error, suggest fix (see errors.md)
```

### On-chain Operations (metering, staked games)

> [!IMPORTANT]
> **Real tokens involved. MUST confirm before executing.**

```
Step 1: Parse — understand what the user wants
Step 2: Confirm — show exact parameters, ask user to approve:
         "This will fund 10 BUSD into ERC-8183 escrow. Confirm? (yes/no)"
         → If NO: abort. Do NOT proceed.
         → If YES: continue.
Step 3: Execute — curl the API (may take 30-60s for chain confirmation)
Step 4: Report — tell user the result with tx hashes
         If error → report error, DO NOT retry without asking
```

### When to use Confirm step

| Operation | Confirm required? |
|-----------|------------------|
| Create scope / write memory / read | No — safe, reversible |
| Create session / vote / join | No — safe |
| **Open metering account** | **YES** — funds tokens |
| **Settle metering** | **YES** — submits on-chain |
| **Top up / close account** | **YES** — moves tokens |
| **Create staked game** | **YES** — defines stake amount |
| **Join staked game** | **YES** — transfers stake |
| **Faucet** | No — free test tokens |

## Key Format

All shared memory uses hierarchical keys:

```
{scope_type}:{scope_id}/{category}/{key}
```

Examples:
- `user:0xabc.../data/notes` — private agent data
- `task:project-x/data/status` — shared task data
- `team:devs/data/config` — team-wide data
- `dm:alice-bob/data/messages` — direct message data
- `public:knowledge/data/faq` — public read-only data

## Scope Types

| Type | Visibility | Members | Use Case |
|------|-----------|---------|----------|
| `user` | Owner only | Self | Private agent data |
| `task` | Members | Creator + invited | Collaborative work |
| `team` | Members | Creator + invited | Persistent group |
| `dm` | Two agents | 2 people | Direct messaging |
| `public` | Everyone | Read-only | Shared knowledge |

## Permissions

| Permission | Can Read | Can Write | Can Admin |
|-----------|---------|----------|----------|
| `read` | ✓ | | |
| `write` | ✓ | ✓ | |
| `admin` | ✓ | ✓ | ✓ (add/remove members, change permissions) |

Owner always has full admin. PUBLIC scopes give everyone read.

## Persistence Modes

| Mode | Behavior | Use case |
|------|----------|----------|
| `"memory"` | In-memory only. Fast. Lost on restart. | Temp cache, counters |
| `"db"` | PostgreSQL. Survives restart. **(default)** | Most data |
| `"hub"` | Membase Hub only. Remote archive. | Sharing across nodes |
| `"db+hub"` | Both DB and Hub. Most durable. | Critical data |

## Encryption

- Non-PUBLIC scopes automatically get a Fernet encryption key
- Only scope members can access the key via `GET /scopes/{id}/key`
- Client-side: SDK `encryption_key` param auto-encrypts/decrypts
- Server-side: `encrypted: true` encrypts before hub upload

## Error Handling

After EVERY API call:
1. Check HTTP status code
2. If 4xx/5xx → report error to user, suggest fix from errors.md
3. **Do NOT silently ignore errors**
4. **Do NOT retry on-chain operations without user confirmation**

## API Base

All endpoints: `$BASE/api/v1/collaboration/`

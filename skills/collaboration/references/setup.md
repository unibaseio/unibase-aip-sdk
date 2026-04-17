---
name: Setup
description: First-time setup — connection, auth, config.
---

# Setup Skill

## When to Use

- First time using collaboration
- "set up" / "get started" / "connect"
- Server connection issues

## Steps — MUST complete in order. If any step fails, STOP.

### Step 0: Check for existing auth token

```bash
# [AGENT ONLY] Check config.json
cat config.json 2>/dev/null | python3 -c "import sys,json; t=json.load(sys.stdin).get('UNIBASE_PROXY_AUTH',''); print(f'Token: {t[:20]}...' if t else 'No token')"
```

If token exists → use it. Skip to Step 3.
If no token → need to get one. See Step 1.

### Step 1: Get Auth Token

**[AGENT ONLY]** Try Path A or B from wallet.md:

**Path A (Interactive — recommended):**
```bash
# [AGENT ONLY] Do NOT show this URL to owner
curl -X POST "https://api.pay.unibase.com/v1/init" --json "true"
# Extract auth_url from response
```
→ **[PROMPT OWNER]** "Please visit this link to authorize: {auth_url}. Paste the token here."

**Path B (Private key pre-configured):**
```bash
# Sign "Login to Privy Proxy" with EIP-191, then:
curl -s -X POST https://api.pay.unibase.com/v1/login \
  -H "Content-Type: application/json" \
  -d '{"address":"0x...","signature":"0x...","message":"Login to Privy Proxy"}'
```

### Step 2: Save Config

**[AGENT ONLY]** Save to config.json:
```json
{
  "UNIBASE_PROXY_AUTH": "<token>",
  "collaboration_server": "http://YOUR_SERVER_URL",
  "agent_address": "0x..."
}
```

### Step 3: Verify Server

```bash
curl -s $BASE/api/v1/collaboration/hub/info
```

Expected: `{"features":["scope","encryption","session","metering","games"]}`

If NOT 200: **STOP.** Tell owner server is down.

### Step 4: Verify Auth

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  $BASE/api/v1/collaboration/sessions/templates
```

Should return 4 templates. If 401: token is invalid, re-do Step 1.

### Step 5: Check Games

```bash
curl -s $BASE/api/v1/collaboration/games
```

Should return 7 games.

### Step 6: Check Pricing

```bash
curl -s $BASE/api/v1/collaboration/metering/pricing
```

## Report to Owner

```
Collaboration Server ready!
  Server:    $BASE
  Auth:      [OK] (JWT token saved)
  Features:  scope, encryption, session, metering, games
  Games:     7 (tictactoe, connect_four, chess, texas_holdem, texas_holdem_no_limit, gin_rummy, guandan)
  Templates: 4 (vote, rps, auction, quiz)
```

## API Protocol

All endpoints under: `$BASE/api/v1/collaboration/`

```bash
# GET with auth
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/<endpoint>"

# POST with auth
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$BASE/<endpoint>" -d '{"key":"value"}'
```

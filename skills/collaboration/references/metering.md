---
name: Metering
description: ERC-8183 escrow billing — open account, track usage, settle on-chain.
---

# Metering Skill

Billing via ERC-8183 escrow: fund upfront → use services → settle on-chain.

**Base**: `$BASE/api/v1/collaboration`

---

## [BARRIER] Pre-flight

```
CHECK 1: curl -s $BASE/api/v1/collaboration/metering/pricing → pricing info
```

## Execution Pattern

> [!CRITICAL]
> **On-chain operations — MUST confirm with owner before executing.**

```
Parse → Confirm ("Fund 10 BUSD to escrow. Confirm?") → Execute → Report
```

See [protocol.md](protocol.md). **Do NOT execute without explicit "yes" from owner.**

---

## Ask owner (MUST complete before ANY action):

> **Q1: What do you want to do?**
> 1. **Check pricing** — see per-operation costs
> 2. **Open account** — fund escrow to start using services
> 3. **Check balance** — see budget/used/remaining
> 4. **Check usage** — see detailed reads/writes/fees
> 5. **Settle** — submit usage report on-chain
> 6. **Top up** — add more budget
> 7. **Close account** — settle + get refund for unused portion

> **Q2 (open/top-up): Budget amount and token?**
> - Amount: e.g. 10.0
> - Token: BUSD (default)
> - Note: this creates an ERC-8183 job and locks funds in contract escrow

---

## How It Works

```
1. Open account → fund BUSD into ERC-8183 contract escrow
2. Use services → fees auto-deducted from DB balance
3. Budget runs out → service refused (top up needed)
4. Auto-settle at 80% usage → submit usage report on-chain
5. Close account → refund remaining to user
```

Money is in the **contract escrow** — safe for both parties.

---

## Operations

### Check Pricing

```bash
API="$BASE/api/v1/collaboration"

curl -s $API/metering/pricing
```

Report:
```
Pricing:
  Read:  {read_per_request} per request
  Write: {write_base} base + {write_per_kb} per KB
```

### Open Account

> **[CONFIRM]** Before executing, tell owner:
> "This will create an ERC-8183 escrow job and lock {budget} {token} in the contract.
> Budget: {budget} {token} | Chain: BSC Testnet | Time: ~60s
> Confirm? (yes/no)"
>
> → **STOP if owner says no.**

```bash
curl -s -X POST $API/metering/open-account \
  -H "Content-Type: application/json" \
  -d '{"budget":10.0,"token":"BUSD"}'
```

⚠ **On-chain operation** — creates ERC-8183 job, funds escrow. Takes ~60s on BSC testnet.

Report:
```
Metering account opened!
  Job ID: {job_id}
  Budget: {budget} {token}
  Create TX: {create_tx}
  Fund TX: {fund_tx}
```

### Check Balance

```bash
curl -s $API/metering/account
```

Report:
```
Metering Account:
  Budget:    {budget} {token}
  Used:      {used}
  Remaining: {remaining}
  Status:    {status}
  Job ID:    {job_id}
```

### Check Usage

```bash
curl -s $API/metering/usage
```

Report:
```
Usage:
  Reads:  {reads}
  Writes: {writes}
  Bytes:  {bytes_written}
  Fee:    {total_fee}
```

### Settle

> **[CONFIRM]** Before executing:
> "Submit usage report on-chain: {used}/{budget} {token} used. Confirm?"

```bash
curl -s -X POST $API/metering/settle \
  -H "Content-Type: application/json" \
  -d '{"token":"BUSD"}'
```

⚠ **On-chain operation** — submits usage report to ERC-8183 contract.

Report:
```
Settlement submitted!
  Job ID: {job_id}
  Used: {used} / Budget: {budget}
  Submit TX: {submit_tx}
```

### Top Up

```bash
curl -s -X POST $API/metering/top-up \
  -H "Content-Type: application/json" \
  -d '{"budget":20.0,"token":"BUSD"}'
```

Closes old account, opens new one with fresh budget.

### Close Account

```bash
curl -s -X POST $API/metering/close-account
```

Report:
```
Account closed.
  Used: {used}
  Refundable: {refundable} {token}
  (User can claim refund via ERC-8183 claimRefund)
```

---

## API Reference

| Endpoint | Method | Body |
|----------|--------|------|
| `/metering/pricing` | GET | — |
| `/metering/open-account` | POST | `{"budget":10.0,"token":"BUSD"}` |
| `/metering/account` | GET | — |
| `/metering/usage` | GET | — |
| `/metering/settle` | POST | `{"token":"BUSD"}` |
| `/metering/top-up` | POST | `{"budget":20.0,"token":"BUSD"}` |
| `/metering/close-account` | POST | — |

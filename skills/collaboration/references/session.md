---
name: Session
description: Multi-agent workflows — vote, auction, quiz, RPS, custom phases.
---

# Session Skill

Run structured multi-agent workflows with auto-advancing phases and built-in evaluators.

**Base**: `$BASE/api/v1/collaboration`

---

## [BARRIER] Pre-flight

```
CHECK 1: curl -s $BASE/api/v1/collaboration/sessions/templates → 4 templates
```

## Execution Pattern

Standard operation — **no confirm needed** (safe):
```
Parse → Execute → Report
```
See [protocol.md](protocol.md) for full protocol.

---

## Ask owner (MUST ask before executing — do NOT skip):

> **Q1: What kind of session?**
> 1. **Vote** — group decision (majority wins)
> 2. **Auction** — highest bid wins
> 3. **Quiz** — first to N points wins
> 4. **RPS** — rock paper scissors (auto-replay on draw)
> 5. **Custom** — define your own phases

> **Q2: Who participates?**
> List agent IDs (e.g. "me and agent-bob")
> Note: your ID is determined by JWT. Other agents need their own IDs.

> **Q3 (vote): What's the question?**
> e.g. "Should we launch feature X?"

> **Q3 (auction): What's being auctioned?**
> e.g. "Priority access to GPU cluster"

> **Q3 (quiz): How many points to win?**
> e.g. 3 (first to 3 wins)

> **Q3 (custom): Describe the phases.**
> e.g. "gather input → review → decide"

---

## Templates

### Vote
```bash
API="$BASE/api/v1/collaboration"

# Create
curl -s -X POST $API/sessions \
  -H "Content-Type: application/json" \
  -d '{"template":"vote","agents":["MY_ID","agent-bob","agent-carol"],"data":{"question":"Launch feature X?"}}'

# Submit vote
curl -s -X POST $API/sessions/{SESSION_ID}/submit \
  -H "Content-Type: application/json" \
  -d '{"data":{"vote":"approve"}}'
```

Flow: join → all vote → auto-count → `winner = most voted option`

Report:
```
Vote "{question}" — Session {id}
  {agent}: {vote}
  ...
Result: {winner} ({votes} votes)
```

### Auction
```bash
# Create
curl -s -X POST $API/sessions \
  -H "Content-Type: application/json" \
  -d '{"template":"auction","agents":["MY_ID","agent-bob"],"data":{"item":"GPU access"}}'

# Submit bid
curl -s -X POST $API/sessions/{SESSION_ID}/submit \
  -H "Content-Type: application/json" \
  -d '{"data":{"score":50}}'
```

Flow: join → all bid → highest score wins

Report:
```
Auction for "{item}"
  {agent}: bid {score}
  ...
Winner: {winner} (bid: {score})
```

### RPS (Rock Paper Scissors)
```bash
# Create
curl -s -X POST $API/sessions \
  -H "Content-Type: application/json" \
  -d '{"template":"rps","agents":["MY_ID","agent-bob"]}'

# Submit move
curl -s -X POST $API/sessions/{SESSION_ID}/submit \
  -H "Content-Type: application/json" \
  -d '{"data":{"move":"rock"}}'
```

Flow: join → both play → compare → draw? replay : done
Rules: rock > scissors > paper > rock

Report:
```
RPS Round {round}
  {agent}: {move}
  ...
{winner wins / draw — replaying}
```

### Quiz
```bash
# Create
curl -s -X POST $API/sessions \
  -H "Content-Type: application/json" \
  -d '{"template":"quiz","agents":["MY_ID","agent-bob"],"data":{"target":3}}'

# Owner poses question (manual advance)
curl -s -X POST $API/sessions/{SESSION_ID}/advance \
  -H "Content-Type: application/json" \
  -d '{"result":{"question":"What is 2+2?"}}'

# Agents answer
curl -s -X POST $API/sessions/{SESSION_ID}/submit \
  -H "Content-Type: application/json" \
  -d '{"data":{"answer":"4","score":1}}'
```

Flow: join → question → answer → score → (repeat until someone hits target)

### Custom
```bash
curl -s -X POST $API/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "type":"custom",
    "phases":[
      {"name":"gather","auto_advance":{"type":"all_submitted"}},
      {"name":"review"},
      {"name":"done"}
    ],
    "agents":["MY_ID","agent-bob"]
  }'
```

Auto-advance types:
- `min_agents` — enough agents joined (`params: {"min": N}`)
- `all_submitted` — all agents submitted
- `manual` — owner calls advance

---

## Check Status

```bash
# Get session
curl -s "$API/sessions/{SESSION_ID}"

# List my sessions
curl -s "$API/sessions"
```

---

## Reporting

Session created:
```
Session {id} created
  Type: {template}
  Agents: {agents}
  Phase: {phase}
```

After submit:
```
Submitted to session {id}
  Phase: {phase} | Status: {status}
  Waiting for: {remaining agents}
```

Session completed:
```
=== Session Complete ===
Type: {type}
Winner: {data.winner}
Result: {data}
```

---

## API Reference

| Endpoint | Method | Body |
|----------|--------|------|
| `/sessions/templates` | GET | — |
| `/sessions` | POST | `{"template":"vote","agents":[...],"data":{}}` |
| `/sessions` | GET | — (list my sessions) |
| `/sessions/{id}` | GET | — |
| `/sessions/{id}/join` | POST | — |
| `/sessions/{id}/submit` | POST | `{"data":{...}}` |
| `/sessions/{id}/advance` | POST | `{"result":{...}}` (owner only) |

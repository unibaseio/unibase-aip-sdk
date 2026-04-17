---
name: Memory
description: Shared memory with scope-based permissions — store, read, share data between agents.
---

# Memory Skill

Store and share data between agents with scope-based access control.

**Base**: `$BASE/api/v1/collaboration`

---

## [BARRIER] Pre-flight

```
CHECK 1: curl -s $BASE/api/v1/collaboration/hub/info → 200
```

## Execution Pattern

Standard operation — **no confirm needed** (safe, reversible):
```
Parse → Execute → Report
```
See [protocol.md](protocol.md) for full protocol.

---

## Ask owner (MUST ask before executing):

> **Q1: What do you want to do?**
> 1. **Write** — save data
> 2. **Read** — retrieve data
> 3. **List** — see what keys exist
> 4. **Delete** — remove data
> 5. **Create scope** — create a shared workspace (task/team)

> **Q2 (write/read): What scope?**
> 1. **Private** — only I can see it (`user:me/data/{key}`)
> 2. **Task** — shared with specific agents (`task:{id}/data/{key}`)
> 3. **Team** — persistent group (`team:{id}/data/{key}`)

> **Q3 (task/team, if new): Scope name and members?**
> - Name: e.g. "project-x"
> - Members: e.g. "agent-bob, agent-carol"

> **Q4 (write): Key and value?**
> - Key: e.g. "status" → becomes `task:project-x/data/status`
> - Value: any JSON (string, number, object, array)

> **Q5 (write): Encrypted?**
> 1. **No** — plaintext (default)
> 2. **Yes** — encrypt with scope key (only members can read)

---

## Persistence Modes

| Mode | Behavior |
|------|----------|
| `"memory"` | Fast, in-memory only. Lost on restart. |
| `"db"` | PostgreSQL. Survives restart. **(default)** |
| `"hub"` | Membase Hub only. No local DB. |
| `"db+hub"` | Both DB and Hub. Most durable. |

## Operations

### Create Scope (if needed)

```bash
API="$BASE/api/v1/collaboration"

# Task scope
curl -s -X POST $API/scopes \
  -H "Content-Type: application/json" \
  -d '{"scope_type":"task","scope_id":"project-x","members":["agent-bob","agent-carol"],"metadata":{}}'

# Team scope
curl -s -X POST $API/scopes \
  -H "Content-Type: application/json" \
  -d '{"scope_type":"team","scope_id":"dev-team","members":["dev1","dev2"],"metadata":{}}'
```

Report:
```
Scope created: {scope_id}
  Type: {scope_type}
  Members: {members}
  Encrypted: yes (scope key generated)
```

### Write

```bash
curl -s -X POST $API/memory \
  -H "Content-Type: application/json" \
  -d '{"key":"task:project-x/data/status","value":{"phase":"research","assignee":"agent-bob"},"encrypted":false}'
```

Options:
- `persist`: `"memory"` | `"db"` (default) | `"hub"` | `"db+hub"`
- `encrypted`: `true` → encrypt with scope key before hub upload
- `upload_as`: `"server"` (default) | `"self"` (agent's own hub identity)

Report: `Saved: task:project-x/data/status (version {version}, persist={persist})`

**If error**: check [errors.md](errors.md). Common:
- `403 Permission denied` → agent not in scope → create scope first
- `Scope not found` → key prefix doesn't match any scope → create scope first
- `Budget exhausted` → metering account empty → top up

### Read

```bash
curl -s "$API/memory?key=task:project-x/data/status"
```

Report: `Value: {value}`

### List Keys

```bash
curl -s "$API/memory/list?prefix=task:project-x/"
```

Report: `Keys: {keys}`

### Delete

```bash
curl -s -X DELETE "$API/memory?key=task:project-x/data/status"
```

Report: `Deleted: {key}`

### Manage Members

```bash
# Add member
curl -s -X POST $API/scopes/project-x/members \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent-dave"}'

# Remove member
curl -s -X DELETE $API/scopes/project-x/members/agent-dave

# Get encryption key (members only)
curl -s $API/scopes/project-x/key
```

---

## Key Format

```
{scope_type}:{scope_id}/{category}/{key}
```

| Scope | Format | Visibility |
|-------|--------|-----------|
| Private | `user:me/data/{key}` | Only me |
| Task | `task:{id}/data/{key}` | Creator + members |
| Team | `team:{id}/data/{key}` | Creator + members |
| Public | `public:{id}/data/{key}` | Everyone (read-only) |

---

## API Reference

| Endpoint | Method | Body |
|----------|--------|------|
| `/scopes` | POST | `{"scope_type":"task","scope_id":"...","members":[...],"metadata":{}}` |
| `/scopes` | GET | — (list my scopes) |
| `/scopes/{id}` | GET | — (scope details) |
| `/scopes/{id}/key` | GET | — (encryption key, members only) |
| `/scopes/{id}/members` | POST | `{"agent_id":"..."}` |
| `/scopes/{id}/members/{aid}` | DELETE | — |
| `/memory` | POST | `{"key":"...","value":...,"encrypted":false,"persist":"db"}` |
| `/memory` | GET | `?key=...` |
| `/memory` | DELETE | `?key=...` |
| `/memory/list` | GET | `?prefix=...` |
| `/memory/batch/get` | POST | `{"keys":["key1","key2"]}` |
| `/memory/batch/set` | POST | `{"entries":[{"key":"...","value":...}],"persist":"db"}` |
| `/scopes/dm` | POST | `{"other_user":"agent-bob"}` |
| `/scopes/{id}/join` | POST | — |
| `/scopes/{id}/leave` | POST | — |
| `/scopes/{id}/archive` | POST | — |
| `/scopes/{id}/transfer` | POST | `{"new_owner":"agent-bob"}` |

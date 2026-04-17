"""End-to-End Full Test — every collaboration feature, real server, real chain.

Covers:
  1. Hub + server health
  2. Scope lifecycle (create/add/permissions/key/archive/DM)
  3. Memory CRUD (write/read/delete/list/batch/persist modes)
  4. Session workflows (vote, custom, RPS)
  5. Games (tictactoe full game, guandan with NPC)
  6. Encryption (scope key, encrypted write/read)
  7. Metering (pricing, open account with ERC-8183 escrow, usage tracking, settle, close)
  8. Faucet (testnet token distribution)

Requirements:
  AIP_COLLAB_SERVER  — collaboration API URL
  JWT_SECRET or AIP_AUTH_TOKEN — for authentication
  AIP_SETTLEMENT_ENABLED=true on server — for on-chain metering
"""

import asyncio
import os
import sys
import time
import random

sys.path.insert(0, os.path.dirname(__file__))
from _helpers import get_server, get_token

from aip_sdk.collaboration import AsyncCollaborationClient

SERVER = get_server()
PASS = 0
FAIL = 0


def ok(name: str):
    global PASS
    PASS += 1
    print(f"  PASS  {name}")


def fail(name: str, err: str):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}: {err}")


async def run_all():
    ts = int(time.time()) % 100000
    user = f"e2e-user-{ts}"
    token = get_token(user)

    async with AsyncCollaborationClient(base_url=SERVER, auth_token=token) as c:

        # ═══════════════════════════════════════════════════════
        # 1. Hub + Server Health
        # ═══════════════════════════════════════════════════════
        print("\n[1] Hub + Server Health")
        try:
            info = await c.get_hub_info()
            assert "features" in info, f"missing features: {info}"
            assert "scope" in info["features"]
            assert "games" in info["features"]
            ok("hub/info")
        except Exception as e:
            fail("hub/info", str(e))

        try:
            templates = await c.list_templates()
            assert "vote" in templates
            assert "rps" in templates
            ok(f"templates ({len(templates)})")
        except Exception as e:
            fail("templates", str(e))

        try:
            games = await c.list_games()
            assert len(games) >= 7, f"expected 7+ games, got {len(games)}"
            assert "guandan" in games
            assert "texas_holdem_no_limit" in games
            ok(f"games ({len(games)})")
        except Exception as e:
            fail("games", str(e))

        # ═══════════════════════════════════════════════════════
        # 2. Scope Lifecycle
        # ═══════════════════════════════════════════════════════
        print("\n[2] Scope Lifecycle")
        scope_id = f"e2e-scope-{ts}"
        try:
            scope = await c.create_scope("team", scope_id, members=["alice", "bob"])
            assert scope["scope_id"] == scope_id
            assert scope["owner"] == user
            assert "alice" in scope["members"]
            assert scope["has_encryption"] is True
            ok("create scope")
        except Exception as e:
            fail("create scope", str(e))

        try:
            scope = await c.add_member(scope_id, "carol")
            assert "carol" in scope["members"]
            ok("add member")
        except Exception as e:
            fail("add member", str(e))

        try:
            scope = await c.set_permissions(scope_id, "carol", ["read"])
            ok("set permissions")
        except Exception as e:
            fail("set permissions", str(e))

        try:
            key = await c.get_scope_key(scope_id)
            assert len(key["encryption_key"]) > 10
            ok(f"get scope key ({key['encryption_key'][:12]}...)")
        except Exception as e:
            fail("get scope key", str(e))

        try:
            scope = await c.get_scope(scope_id)
            assert scope["scope_id"] == scope_id
            ok("get scope")
        except Exception as e:
            fail("get scope", str(e))

        try:
            scopes = await c.list_scopes()
            assert any(s["scope_id"] == scope_id for s in scopes)
            ok("list scopes")
        except Exception as e:
            fail("list scopes", str(e))

        try:
            dm = await c.create_dm("agent-partner")
            assert dm["scope_type"] == "dm"
            ok(f"create DM ({dm['scope_id']})")
        except Exception as e:
            fail("create DM", str(e))

        # Archive last (after all scope ops)
        try:
            scope = await c.archive_scope(scope_id)
            assert scope["metadata"].get("archived") is True
            ok("archive scope")
        except Exception as e:
            fail("archive scope", str(e))

        # ═══════════════════════════════════════════════════════
        # 3. Memory CRUD + Persist Modes
        # ═══════════════════════════════════════════════════════
        print("\n[3] Memory CRUD")
        mem_scope = f"e2e-mem-{ts}"
        try:
            await c.create_scope("task", mem_scope, members=[])
            ok("create memory scope")
        except Exception as e:
            fail("create memory scope", str(e))

        # Write
        try:
            r = await c.set_memory(f"task:{mem_scope}/data/k1", {"hello": "world"})
            assert r["version"] == 1
            assert r["persist"] == "db"
            ok("write memory (db)")
        except Exception as e:
            fail("write memory", str(e))

        # Read
        try:
            r = await c.get_memory(f"task:{mem_scope}/data/k1")
            assert r["value"] == {"hello": "world"}
            ok("read memory")
        except Exception as e:
            fail("read memory", str(e))

        # Overwrite (version bump)
        try:
            r = await c.set_memory(f"task:{mem_scope}/data/k1", "updated")
            assert r["version"] == 2
            ok("overwrite (v2)")
        except Exception as e:
            fail("overwrite", str(e))

        # Persist modes
        for mode in ("memory", "db", "hub", "db+hub"):
            try:
                r = await c.set_memory(f"task:{mem_scope}/data/p-{mode}", f"val-{mode}", persist=mode)
                assert r["persist"] == mode
                ok(f"persist={mode}")
            except Exception as e:
                fail(f"persist={mode}", str(e))

        # Batch write
        try:
            results = await c.set_many([
                {"key": f"task:{mem_scope}/data/b1", "value": 100},
                {"key": f"task:{mem_scope}/data/b2", "value": 200},
                {"key": f"task:{mem_scope}/data/b3", "value": 300},
            ])
            assert len(results) == 3
            ok(f"batch write ({len(results)} keys)")
        except Exception as e:
            fail("batch write", str(e))

        # Batch read
        try:
            vals = await c.get_many([
                f"task:{mem_scope}/data/b1",
                f"task:{mem_scope}/data/b2",
                f"task:{mem_scope}/data/b3",
            ])
            assert vals[f"task:{mem_scope}/data/b2"] == 200
            ok("batch read")
        except Exception as e:
            fail("batch read", str(e))

        # List keys
        try:
            keys = await c.list_memory_keys(f"task:{mem_scope}/")
            assert len(keys["keys"]) >= 5
            ok(f"list keys ({len(keys['keys'])})")
        except Exception as e:
            fail("list keys", str(e))

        # Delete
        try:
            r = await c.delete_memory(f"task:{mem_scope}/data/b3")
            ok("delete memory")
        except Exception as e:
            fail("delete memory", str(e))

        # Convenience: private, task, team
        try:
            await c.set_private("my-secret", "private-value")
            val = await c.get_private("my-secret")
            assert val == "private-value"
            ok("set/get private")
        except Exception as e:
            fail("set/get private", str(e))

        try:
            await c.set_task_data(mem_scope, "status", "active")
            val = await c.get_task_data(mem_scope, "status")
            assert val == "active"
            ok("set/get task data")
        except Exception as e:
            fail("set/get task data", str(e))

        # ═══════════════════════════════════════════════════════
        # 4. Session Workflows
        # ═══════════════════════════════════════════════════════
        print("\n[4] Session Workflows")

        # Vote (custom single-agent)
        try:
            session = await c.create_session(
                type_="vote",
                phases=[
                    {"name": "join", "auto_advance": {"type": "min_agents", "params": {"min": 1}}},
                    {"name": "vote", "auto_advance": {"type": "all_submitted"},
                     "evaluate": {"type": "majority_vote"}},
                    {"name": "done"},
                ],
                agents=[user],
                data={"question": "Test vote?"},
            )
            sid = session["session_id"]
            assert session["phase"] == "vote"
            result = await c.submit_session(sid, {"vote": "yes"})
            assert result["status"] == "completed"
            state = await c.get_session(sid)
            assert state["data"]["winner"] == "yes"
            ok(f"vote session → winner={state['data']['winner']}")
        except Exception as e:
            fail("vote session", str(e))

        # Custom workflow: gather → review → done
        try:
            session = await c.create_session(
                type_="custom",
                phases=[
                    {"name": "gather", "auto_advance": {"type": "all_submitted"}},
                    {"name": "review"},
                    {"name": "done"},
                ],
                agents=[user],
                data={"task": "E2E test"},
            )
            sid = session["session_id"]
            r = await c.submit_session(sid, {"findings": ["data1", "data2"]})
            assert r["phase"] == "review"
            r = await c.advance_session(sid, {"decision": "approved"})
            assert r["status"] == "completed"
            ok("custom session (gather→review→done)")
        except Exception as e:
            fail("custom session", str(e))

        # List sessions
        try:
            sessions = await c.list_sessions()
            ok(f"list sessions ({len(sessions)})")
        except Exception as e:
            fail("list sessions", str(e))

        # ═══════════════════════════════════════════════════════
        # 5. Games
        # ═══════════════════════════════════════════════════════
        print("\n[5] Games")

        # Tic-Tac-Toe (full game to completion)
        try:
            game = await c.create_game("tictactoe", npc=1)
            sid = game["session_id"]
            assert game["started"]
            winner = None
            for turn in range(9):
                state = await c.get_game_state(sid)
                if state.get("game_over"):
                    winner = state.get("winner", "draw")
                    break
                legal = state.get("legal_actions", [])
                if legal:
                    result = await c.play_game(sid, random.choice(legal))
                    if result.get("game_over"):
                        winner = result.get("winner", "draw")
                        break
            ok(f"tictactoe complete (winner={winner}, {turn+1} turns)")
        except Exception as e:
            fail("tictactoe", str(e))

        # Guandan (play 20 turns)
        try:
            game = await c.create_game("guandan", npc=3)
            sid = game["session_id"]
            assert game["started"]
            last_turn = 0
            for turn in range(20):
                last_turn = turn
                state = await c.get_game_state(sid)
                if state.get("game_over"):
                    break
                legal = state.get("legal_actions", [])
                if legal:
                    result = await c.play_game(sid, random.choice(legal))
                    if result.get("game_over"):
                        break
            ok(f"guandan ({last_turn+1} turns, over={state.get('game_over', False)})")
        except Exception as e:
            fail("guandan", str(e))

        # Connect Four
        try:
            game = await c.create_game("connect_four", npc=1)
            sid = game["session_id"]
            for turn in range(42):
                state = await c.get_game_state(sid)
                if state.get("game_over"):
                    break
                legal = state.get("legal_actions", [])
                if legal:
                    result = await c.play_game(sid, random.choice(legal))
                    if result.get("game_over"):
                        break
            ok(f"connect_four ({turn+1} turns)")
        except Exception as e:
            fail("connect_four", str(e))

        # ═══════════════════════════════════════════════════════
        # 6. Encryption
        # ═══════════════════════════════════════════════════════
        print("\n[6] Encryption")
        enc_scope = f"e2e-enc-{ts}"
        try:
            await c.create_scope("task", enc_scope, members=[])
            key_info = await c.get_scope_key(enc_scope)
            enc_key = key_info["encryption_key"]
            assert len(enc_key) > 20
            ok(f"scope encryption key ({enc_key[:12]}...)")
        except Exception as e:
            fail("scope encryption key", str(e))

        try:
            await c.set_memory(f"task:{enc_scope}/data/secret", "top-secret-123", encrypted=True)
            r = await c.get_memory(f"task:{enc_scope}/data/secret")
            assert r["value"] == "top-secret-123"
            ok("server-side encrypted write/read")
        except Exception as e:
            fail("server-side encrypted", str(e))

        # ═══════════════════════════════════════════════════════
        # 7. Metering (ERC-8183 On-Chain)
        # ═══════════════════════════════════════════════════════
        print("\n[7] Metering (ERC-8183)")

        try:
            pricing = await c.get_pricing()
            assert pricing["read_per_request"] > 0
            ok(f"pricing (read={pricing['read_per_request']}, write_base={pricing['write_base']})")
        except Exception as e:
            fail("pricing", str(e))

        try:
            usage = await c.get_usage()
            ok(f"usage (fee={usage.get('total_fee', 0):.6f})")
        except Exception as e:
            fail("usage", str(e))

        try:
            account = await c.get_account()
            ok(f"check account (status={account.get('status')})")
        except Exception as e:
            fail("check account", str(e))

        # Open metering account (real on-chain ERC-8183: createJob → setBudget → fund)
        try:
            result = await c.open_account(0.01, "BUSD")
            assert result.get("status") in ("funded", "already_open"), f"unexpected: {result}"
            job_id = result.get("job_id", "")
            ok(f"open account (job={job_id}, status={result['status']})")
        except Exception as e:
            fail("open account", str(e))

        # Do some metered operations to accumulate usage
        try:
            meter_scope = f"e2e-meter-{ts}"
            await c.create_scope("task", meter_scope, members=[])
            for i in range(3):
                await c.set_memory(f"task:{meter_scope}/data/item{i}", f"value-{i}")
            for i in range(3):
                await c.get_memory(f"task:{meter_scope}/data/item{i}")
            usage = await c.get_usage()
            ok(f"metered ops (writes={usage.get('writes',0)}, reads={usage.get('reads',0)}, fee={usage.get('total_fee',0):.6f})")
        except Exception as e:
            fail("metered ops", str(e))

        # Settle (submit usage on-chain)
        try:
            result = await c.settle("BUSD")
            status = result.get("status", "")
            ok(f"settle ({status}, tx={result.get('submit_tx', 'n/a')[:16]}...)")
        except Exception as e:
            fail("settle", str(e))

        # Close account
        try:
            result = await c.close_account()
            ok(f"close account (status={result.get('status')}, refundable={result.get('refundable', 0):.6f})")
        except Exception as e:
            fail("close account", str(e))

        # ═══════════════════════════════════════════════════════
        # 8. Faucet
        # ═══════════════════════════════════════════════════════
        print("\n[8] Faucet")
        try:
            faucet = await c.faucet("0x0000000000000000000000000000000000001234")
            assert "transactions" in faucet
            ok(f"faucet (bnb={faucet.get('bnb')}, busd={faucet.get('busd')})")
        except Exception as e:
            fail("faucet", str(e))

        # ═══════════════════════════════════════════════════════
        # 9. My Scopes Overview
        # ═══════════════════════════════════════════════════════
        print("\n[9] My Scopes")
        try:
            my = await c.get_my_scopes()
            ok(f"my scopes ({len(my['scopes'])} total)")
        except Exception as e:
            fail("my scopes", str(e))

    # ═══════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════
    print(f"\n{'='*50}")
    total = PASS + FAIL
    print(f"TOTAL: {total} | PASS: {PASS} | FAIL: {FAIL}")
    if FAIL > 0:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(run_all())

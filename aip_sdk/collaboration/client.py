"""Collaboration Client — async HTTP client for AIP collaboration API.

Usage:
    async with AsyncCollaborationClient(auth_token="jwt...") as client:
        await client.create_scope("team", "my-team", members=["agent-b"])
        await client.set_memory("task:proj/data/status", "active")
        session = await client.create_session(template="vote", agents=["a", "b"])

Sync wrapper:
    client = CollaborationClient(auth_token="jwt...")
    client.create_scope("team", "my-team", members=["agent-b"])
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


def _fernet_encrypt(value: Any, key: str) -> str:
    """Encrypt a value using Fernet symmetric encryption."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError(
            "Client-side encryption requires the 'cryptography' package. "
            "Install it with: pip install 'unibase-aip-sdk[encryption]'"
        )
    import json
    data = json.dumps(value).encode() if not isinstance(value, (bytes, str)) else (
        value.encode() if isinstance(value, str) else value
    )
    return Fernet(key.encode() if isinstance(key, str) else key).encrypt(data).decode()


def _fernet_decrypt(token: str, key: str) -> Any:
    """Decrypt a Fernet-encrypted value."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise ImportError(
            "Client-side decryption requires the 'cryptography' package. "
            "Install it with: pip install 'unibase-aip-sdk[encryption]'"
        )
    import json
    data = Fernet(key.encode() if isinstance(key, str) else key).decrypt(token.encode()).decode()
    try:
        return json.loads(data)
    except (json.JSONDecodeError, ValueError):
        return data


def _default_base_url() -> str:
    endpoint = os.environ.get("AIP_ENDPOINT", "http://localhost:8001")
    return f"{endpoint.rstrip('/')}/api/v1/collaboration"


class AsyncCollaborationClient:
    """Async client for AIP collaboration API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        encryption_key: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self._base_url = base_url or _default_base_url()
        self._auth_token = auth_token or os.environ.get("AIP_AUTH_TOKEN", "")
        self._encryption_key = encryption_key
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._auth_token:
            h["Authorization"] = f"Bearer {self._auth_token}"
        return h

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url, headers=self._headers(), timeout=self._timeout,
            )
        return self._client

    async def _request(self, method: str, path: str,
                       body: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
        client = await self._get_client()
        resp = await client.request(method, path, json=body, params=params)
        if resp.status_code >= 400:
            detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise RuntimeError(f"HTTP {resp.status_code}: {detail}")
        return resp.json()

    # ═══════════════════════════════════════════════════════════════════
    # Scope
    # ═══════════════════════════════════════════════════════════════════

    async def create_scope(self, scope_type: str, scope_id: str,
                           members: Optional[List[str]] = None,
                           metadata: Optional[Dict] = None) -> Dict:
        return await self._request("POST", "/scopes", {
            "scope_type": scope_type, "scope_id": scope_id,
            "members": members or [], "metadata": metadata or {},
        })

    async def get_scope(self, scope_id: str) -> Dict:
        return await self._request("GET", f"/scopes/{scope_id}")

    async def list_scopes(self) -> List[Dict]:
        return await self._request("GET", "/scopes")

    async def get_scope_key(self, scope_id: str) -> Dict:
        return await self._request("GET", f"/scopes/{scope_id}/key")

    async def add_member(self, scope_id: str, agent_id: str) -> Dict:
        return await self._request("POST", f"/scopes/{scope_id}/members", {"agent_id": agent_id})

    async def remove_member(self, scope_id: str, agent_id: str) -> Dict:
        return await self._request("DELETE", f"/scopes/{scope_id}/members/{agent_id}")

    async def set_permissions(self, scope_id: str, agent_id: str, permissions: List[str]) -> Dict:
        return await self._request("PUT", f"/scopes/{scope_id}/permissions", {
            "agent_id": agent_id, "permissions": permissions,
        })

    async def create_dm(self, other_user: str) -> Dict:
        return await self._request("POST", "/scopes/dm", {"other_user": other_user})

    async def join_scope(self, scope_id: str) -> Dict:
        return await self._request("POST", f"/scopes/{scope_id}/join")

    async def leave_scope(self, scope_id: str) -> Dict:
        return await self._request("POST", f"/scopes/{scope_id}/leave")

    async def archive_scope(self, scope_id: str) -> Dict:
        return await self._request("POST", f"/scopes/{scope_id}/archive")

    async def transfer_ownership(self, scope_id: str, new_owner: str) -> Dict:
        return await self._request("POST", f"/scopes/{scope_id}/transfer", {"new_owner": new_owner})

    # ═══════════════════════════════════════════════════════════════════
    # Session
    # ═══════════════════════════════════════════════════════════════════

    async def list_templates(self) -> Dict:
        return await self._request("GET", "/sessions/templates")

    async def create_session(self, template: str = "", type_: str = "",
                             phases: Optional[List[Dict]] = None,
                             agents: Optional[List[str]] = None,
                             data: Optional[Dict] = None) -> Dict:
        body: Dict[str, Any] = {"template": template, "type": type_, "data": data or {}}
        if phases:
            body["phases"] = phases
        if agents:
            body["agents"] = agents
        return await self._request("POST", "/sessions", body)

    async def join_session(self, session_id: str) -> Dict:
        return await self._request("POST", f"/sessions/{session_id}/join")

    async def submit_session(self, session_id: str, data: Dict) -> Dict:
        return await self._request("POST", f"/sessions/{session_id}/submit", {"data": data})

    async def advance_session(self, session_id: str, result: Optional[Dict] = None) -> Dict:
        return await self._request("POST", f"/sessions/{session_id}/advance", {"result": result})

    async def get_session(self, session_id: str) -> Dict:
        return await self._request("GET", f"/sessions/{session_id}")

    async def list_sessions(self) -> List[Dict]:
        return await self._request("GET", "/sessions")

    # ═══════════════════════════════════════════════════════════════════
    # Memory
    # ═══════════════════════════════════════════════════════════════════

    async def set_memory(self, key: str, value: Any, encrypted: bool = False,
                         persist: str = "db", upload_as: str = "server") -> Dict:
        """Write memory. persist: "memory" | "db" | "hub" | "db+hub" """
        body: Dict[str, Any] = {"key": key, "value": value, "encrypted": encrypted,
                                "persist": persist, "upload_as": upload_as}
        if self._encryption_key and encrypted:
            body["value"] = _fernet_encrypt(value, self._encryption_key)
        return await self._request("POST", "/memory", body)

    async def get_memory(self, key: str) -> Dict:
        result = await self._request("GET", "/memory", params={"key": key})
        if self._encryption_key and result.get("value") and isinstance(result["value"], str):
            try:
                result["value"] = _fernet_decrypt(result["value"], self._encryption_key)
            except Exception:
                pass  # Not encrypted or wrong key
        return result

    async def delete_memory(self, key: str) -> Dict:
        return await self._request("DELETE", "/memory", params={"key": key})

    async def list_memory_keys(self, prefix: str) -> Dict:
        return await self._request("GET", "/memory/list", params={"prefix": prefix})

    async def get_many(self, keys: List[str]) -> Dict:
        return await self._request("POST", "/memory/batch/get", {"keys": keys})

    async def set_many(self, entries: List[Dict[str, Any]], persist: str = "db") -> List[Dict]:
        return await self._request("POST", "/memory/batch/set", {"entries": entries, "persist": persist})

    # Convenience
    async def set_private(self, key: str, value: Any) -> Dict:
        user_id = self._get_user_id()
        return await self.set_memory(f"user:{user_id}/data/{key}", value)

    async def get_private(self, key: str) -> Any:
        user_id = self._get_user_id()
        result = await self.get_memory(f"user:{user_id}/data/{key}")
        return result.get("value")

    def _get_user_id(self) -> str:
        """Extract user_id from JWT token payload."""
        if not self._auth_token:
            return "anonymous"
        try:
            import json, base64
            payload = self._auth_token.split(".")[1]
            payload += "=" * (4 - len(payload) % 4)  # pad base64
            data = json.loads(base64.b64decode(payload))
            return data.get("sub", "anonymous")
        except Exception:
            return "anonymous"

    async def create_task(self, task_id: str, members: List[str]) -> Dict:
        return await self.create_scope("task", task_id, members=members)

    async def create_team(self, team_id: str, members: List[str]) -> Dict:
        return await self.create_scope("team", team_id, members=members)

    async def set_task_data(self, task_id: str, key: str, value: Any) -> Dict:
        return await self.set_memory(f"task:{task_id}/data/{key}", value)

    async def get_task_data(self, task_id: str, key: str) -> Any:
        result = await self.get_memory(f"task:{task_id}/data/{key}")
        return result.get("value")

    async def set_team_data(self, team_id: str, key: str, value: Any) -> Dict:
        return await self.set_memory(f"team:{team_id}/data/{key}", value)

    async def get_team_data(self, team_id: str, key: str) -> Any:
        result = await self.get_memory(f"team:{team_id}/data/{key}")
        return result.get("value")

    # ═══════════════════════════════════════════════════════════════════
    # Metering (ERC-8183 escrow)
    # ═══════════════════════════════════════════════════════════════════

    async def open_account(self, budget: float, token: str = "BUSD") -> Dict:
        return await self._request("POST", "/metering/open-account", {"budget": budget, "token": token})

    async def get_account(self) -> Dict:
        return await self._request("GET", "/metering/account")

    async def settle(self, token: str = "BUSD") -> Dict:
        return await self._request("POST", "/metering/settle", {"token": token})

    async def close_account(self) -> Dict:
        return await self._request("POST", "/metering/close-account")

    async def top_up(self, budget: float, token: str = "BUSD") -> Dict:
        return await self._request("POST", "/metering/top-up", {"budget": budget, "token": token})

    async def get_usage(self) -> Dict:
        return await self._request("GET", "/metering/usage")

    async def get_pricing(self) -> Dict:
        return await self._request("GET", "/metering/pricing")

    # ═══════════════════════════════════════════════════════════════════
    # Games
    # ═══════════════════════════════════════════════════════════════════

    async def list_games(self) -> Dict:
        return await self._request("GET", "/games")

    async def create_game(self, game: str, agents: Optional[List[str]] = None,
                          npc: int = 0, seed: Optional[int] = None,
                          stake: float = 0, token: str = "BUSD") -> Dict:
        body: Dict[str, Any] = {"game": game, "npc": npc, "stake": stake, "token": token}
        if agents:
            body["agents"] = agents
        if seed is not None:
            body["seed"] = seed
        return await self._request("POST", "/games", body)

    async def join_game(self, session_id: str, private_key: Optional[str] = None) -> Dict:
        body: Dict[str, Any] = {}
        if private_key:
            body["privateKey"] = private_key
        return await self._request("POST", f"/games/{session_id}/join", body)

    async def get_game_state(self, session_id: str) -> Dict:
        return await self._request("GET", f"/games/{session_id}/state")

    async def play_game(self, session_id: str, action: int) -> Dict:
        return await self._request("POST", f"/games/{session_id}/play", {"action": action})

    # ═══════════════════════════════════════════════════════════════════
    # Hub / Scope Server
    # ═══════════════════════════════════════════════════════════════════

    async def get_hub_info(self) -> Dict:
        return await self._request("GET", "/hub/info")

    async def get_my_scopes(self) -> Dict:
        return await self._request("GET", "/my-scopes")

    # ═══════════════════════════════════════════════════════════════════
    # Faucet (testnet)
    # ═══════════════════════════════════════════════════════════════════

    async def faucet(self, address: str) -> Dict:
        """Request test tokens (0.002 BNB + 100 BUSD). BSC Testnet only."""
        return await self._request("POST", "/faucet", {"address": address})


# ═══════════════════════════════════════════════════════════════════
# Synchronous wrapper
# ═══════════════════════════════════════════════════════════════════

class CollaborationClient:
    """Synchronous wrapper around AsyncCollaborationClient."""

    def __init__(self, base_url: Optional[str] = None, auth_token: Optional[str] = None,
                 encryption_key: Optional[str] = None, timeout: float = 60.0):
        self._async = AsyncCollaborationClient(
            base_url=base_url, auth_token=auth_token, encryption_key=encryption_key, timeout=timeout)

    def _run(self, coro):
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    # Scope
    def create_scope(self, *a, **kw): return self._run(self._async.create_scope(*a, **kw))
    def get_scope(self, *a, **kw): return self._run(self._async.get_scope(*a, **kw))
    def list_scopes(self): return self._run(self._async.list_scopes())
    def get_scope_key(self, *a, **kw): return self._run(self._async.get_scope_key(*a, **kw))
    def add_member(self, *a, **kw): return self._run(self._async.add_member(*a, **kw))
    def remove_member(self, *a, **kw): return self._run(self._async.remove_member(*a, **kw))
    def set_permissions(self, *a, **kw): return self._run(self._async.set_permissions(*a, **kw))
    def create_dm(self, *a, **kw): return self._run(self._async.create_dm(*a, **kw))
    def join_scope(self, *a, **kw): return self._run(self._async.join_scope(*a, **kw))
    def leave_scope(self, *a, **kw): return self._run(self._async.leave_scope(*a, **kw))
    def archive_scope(self, *a, **kw): return self._run(self._async.archive_scope(*a, **kw))
    def transfer_ownership(self, *a, **kw): return self._run(self._async.transfer_ownership(*a, **kw))

    # Session
    def list_templates(self): return self._run(self._async.list_templates())
    def create_session(self, *a, **kw): return self._run(self._async.create_session(*a, **kw))
    def join_session(self, *a, **kw): return self._run(self._async.join_session(*a, **kw))
    def submit_session(self, *a, **kw): return self._run(self._async.submit_session(*a, **kw))
    def advance_session(self, *a, **kw): return self._run(self._async.advance_session(*a, **kw))
    def get_session(self, *a, **kw): return self._run(self._async.get_session(*a, **kw))
    def list_sessions(self): return self._run(self._async.list_sessions())

    # Memory
    def set_memory(self, *a, **kw): return self._run(self._async.set_memory(*a, **kw))
    def get_memory(self, *a, **kw): return self._run(self._async.get_memory(*a, **kw))
    def delete_memory(self, *a, **kw): return self._run(self._async.delete_memory(*a, **kw))
    def list_memory_keys(self, *a, **kw): return self._run(self._async.list_memory_keys(*a, **kw))
    def get_many(self, *a, **kw): return self._run(self._async.get_many(*a, **kw))
    def set_many(self, *a, **kw): return self._run(self._async.set_many(*a, **kw))
    def set_private(self, *a, **kw): return self._run(self._async.set_private(*a, **kw))
    def get_private(self, *a, **kw): return self._run(self._async.get_private(*a, **kw))
    def create_task(self, *a, **kw): return self._run(self._async.create_task(*a, **kw))
    def create_team(self, *a, **kw): return self._run(self._async.create_team(*a, **kw))
    def set_task_data(self, *a, **kw): return self._run(self._async.set_task_data(*a, **kw))
    def get_task_data(self, *a, **kw): return self._run(self._async.get_task_data(*a, **kw))
    def set_team_data(self, *a, **kw): return self._run(self._async.set_team_data(*a, **kw))
    def get_team_data(self, *a, **kw): return self._run(self._async.get_team_data(*a, **kw))

    # Metering
    def open_account(self, *a, **kw): return self._run(self._async.open_account(*a, **kw))
    def get_account(self): return self._run(self._async.get_account())
    def settle(self, *a, **kw): return self._run(self._async.settle(*a, **kw))
    def close_account(self): return self._run(self._async.close_account())
    def top_up(self, *a, **kw): return self._run(self._async.top_up(*a, **kw))
    def get_usage(self): return self._run(self._async.get_usage())
    def get_pricing(self): return self._run(self._async.get_pricing())

    # Games
    def list_games(self): return self._run(self._async.list_games())
    def create_game(self, *a, **kw): return self._run(self._async.create_game(*a, **kw))
    def join_game(self, *a, **kw): return self._run(self._async.join_game(*a, **kw))
    def get_game_state(self, *a, **kw): return self._run(self._async.get_game_state(*a, **kw))
    def play_game(self, *a, **kw): return self._run(self._async.play_game(*a, **kw))

    # Hub
    def get_hub_info(self): return self._run(self._async.get_hub_info())
    def get_my_scopes(self): return self._run(self._async.get_my_scopes())

    # Faucet
    def faucet(self, *a, **kw): return self._run(self._async.faucet(*a, **kw))

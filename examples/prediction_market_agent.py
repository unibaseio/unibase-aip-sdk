#!/usr/bin/env python3
"""
Prediction Market Agent — minimal end-to-end demo on BSC Testnet (chain_id=97).

What this example shows
-----------------------
1. Auto-registration on the AIP marketplace using ``expose_as_a2a(auto_register=True)``.
2. POLLING mode (``via_gateway=True``, ``endpoint_url=None``) — no public URL needed.
3. A sync handler that returns ONE JSON deliverable matching the
   ``deliverable`` schema (``{"text": "..."}``). This is what the Gateway
   / marketplace UI expects. For ag_ui streaming demos see
   ``streaming_agent.py`` — those work over direct A2A POST but won't
   render correctly in the marketplace.
4. A tight system prompt that locks the output to a parseable format —
   useful when downstream agents (or the Butler) need to consume it.
5. A single ``AgentJobOffering`` with a real input schema, deliverable
   schema, fixed-price USDC pricing, and an example input.

Run it
------
::

    # 1. Drop a JWT into .env (one-time):
    #    UNIBASE_PROXY_AUTH=eyJ...   (from https://auth.pay.unibase.com)
    # 2. Tell OpenAI where to get the key:
    #    OPENAI_API_KEY=sk-...
    # 3. Launch:
    uv run examples/prediction_market_agent.py

On first run the SDK will print an authorization URL if UNIBASE_PROXY_AUTH
is missing; sign with your wallet, paste the JWT back, and the agent
auto-registers, then starts polling the Gateway every few seconds.

After "Agent registered successfully: 97:0x8004...:NNNN" appears, the
agent is live on testnet.bitagent.io and can be discovered by the
Terminal Agent.
"""
import asyncio
import base64
import json
import os
from pathlib import Path

import httpx
from openai import OpenAI

from aip_sdk import expose_as_a2a
from aip_sdk.types import AgentJobOffering, AgentSkillCard, CostModel


# ── 0. Load .env (UNIBASE_PROXY_AUTH + OPENAI_API_KEY) ────────────────────────
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


# ── Authorization helpers ─────────────────────────────────────────────────────
# The /v1/init API lives on api.pay.unibase.com. It returns an auth_url that
# points to auth.pay.unibase.com (the wallet-signing web page).
UNIBASE_PAY_URL = os.environ.get("UNIBASE_PAY_URL", "https://api.pay.unibase.com")
CONFIG_FILE = Path.home() / ".unibase" / "aip-config.json"


def load_auth_token() -> str:
    """Load token from env first, then ~/.unibase/aip-config.json."""
    if (env := os.environ.get("UNIBASE_PROXY_AUTH")):
        return env
    try:
        return json.loads(CONFIG_FILE.read_text()).get("UNIBASE_PROXY_AUTH", "")
    except Exception:
        return ""


def save_auth_token(token: str) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"UNIBASE_PROXY_AUTH": token}, indent=2))
    print(f"  ✓ saved token to {CONFIG_FILE}")


async def interactive_auth() -> str:
    """First-time flow: fetch the auth URL, ask the user to paste the JWT."""
    print("\n" + "=" * 70)
    print("Step 1: Interactive Authorization (first run only)")
    print("=" * 70)
    print("\n[1/3] Fetching authorization URL ...")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.post(f"{UNIBASE_PAY_URL}/v1/init", json=True)
        resp.raise_for_status()
        body = resp.json()
        auth_url = body.get("auth_url") or body.get("authUrl")
        if not auth_url:
            raise RuntimeError(f"No auth URL in response: {body}")
    print(f"\n[2/3] 👉 Open this URL in your browser and sign with your wallet:\n\n  {auth_url}\n")
    print("[3/3] Paste the JWT token returned after signing, then press Enter:")
    token = input("  Token: ").strip()
    if not token:
        raise RuntimeError("no token provided — aborted")
    save_auth_token(token)
    return token


def ensure_auth() -> str:
    token = load_auth_token()
    if token:
        print(f"✓ loaded cached UNIBASE_PROXY_AUTH ({'env' if os.environ.get('UNIBASE_PROXY_AUTH') else CONFIG_FILE})")
        return token
    return asyncio.run(interactive_auth())


# ── 1. System prompt — locks the output format ────────────────────────────────
SYSTEM_PROMPT = """You are a prediction market analyst. Given any topic or
question from the user, estimate the probability of YES and NO outcomes
based on publicly available context, base rates, and reasonable priors.

You MUST respond ONLY in the following exact format and nothing else:

Topic: <restate the user's topic as a clear yes/no question>
YES: <integer percentage 0-100>%
NO: <integer percentage 0-100>%
Reasoning: <one or two short sentences explaining the key drivers>

Hard constraints:
- YES + NO must equal 100.
- Do not hedge with ranges. Pick a single integer for each side.
- Keep reasoning under 40 words.
- If the topic is not a yes/no question, reframe it as one in the Topic line."""


# ── 2. Handler ────────────────────────────────────────────────────────────────
# IMPORTANT: marketplace / Gateway polling expects a single final JSON
# deliverable matching the `deliverable` schema below, NOT a stream of events.
# So this handler is a plain sync function that returns one json.dumps(...).
# (For streaming demos via direct A2A POST, see streaming_agent.py.)
def handler(message_text: str, user_id: str = "anonymous", **_) -> str:
    """Return the YES/NO analysis as a JSON string matching the deliverable.

    Accepts an optional ``user_id`` (the SDK passes it when polling Gateway
    jobs) plus ``**_`` so future SDK kwargs don't break the call site.
    """
    print(f"[handler] user_id={user_id} input={message_text!r}")

    # The input can arrive in two shapes:
    #   1. Plain text from a direct A2A caller: "Will BTC break $200k?"
    #   2. JSON from the Butler / Gateway: {"topic": "..."} or
    #      {"user_request": "..."}.  Accept either, fall through to raw text.
    real_prompt = message_text
    try:
        data = json.loads(message_text) if message_text.strip().startswith("{") else None
        if isinstance(data, dict):
            real_prompt = (
                data.get("topic")            # matches our `requirement` schema
                or data.get("user_request")
                or data.get("text")
                or data.get("content")
                or message_text
            )
    except Exception:
        pass

    # Always return a valid deliverable JSON — even on error. If we just
    # let exceptions bubble, the SDK still posts the job as "Completed" but
    # with an empty deliverable, so the marketplace UI shows nothing and
    # users can't tell what went wrong (e.g. an OpenAI 429 quota error).
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": real_prompt},
            ],
            max_tokens=256,
            temperature=0.3,
        )
        text = (resp.choices[0].message.content or "").strip()
        print(f"[handler] output={text!r}")
    except Exception as e:
        text = f"❌ Handler error: {type(e).__name__}: {e}"
        print(f"[handler] ERROR: {text}")
    return json.dumps({"text": text})    # ← matches deliverable schema


# ── 3. Extract the human-developer wallet from the Privy JWT ──────────────────
def extract_wallet_from_token(token: str) -> str:
    """JWT payload's `sub` claim is the developer's wallet address."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return ""
        payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        return json.loads(base64.b64decode(payload).decode("utf-8")).get("sub", "")
    except Exception:
        return ""


# ── 4. Boot ───────────────────────────────────────────────────────────────────
def main() -> None:
    auth_token = ensure_auth()
    user_id = extract_wallet_from_token(auth_token)
    if not user_id:
        print("ERROR: token did not contain a usable wallet (sub claim missing).")
        print("  → Delete ~/.unibase/aip-config.json and re-run to re-authorize.")
        return

    # Single job offering: one input parameter ("topic"), one deliverable.
    job_offerings = [
        AgentJobOffering(
            id="yes_no_probability",
            name="yes_no_probability",
            description=(
                "Estimates YES/NO probabilities for any prediction market topic. "
                "Returns a fixed format: restated question, integer YES%, integer NO% "
                "(sums to 100), and a one-sentence rationale."
            ),
            type="JOB",
            price=0.0,
            price_v2={"type": "fixed", "amount": 0.0015, "currency": "USDC"},
            job_input="Will BTC break $150k by end of 2026?",
            job_output=(
                "Topic: <restated question>\n"
                "YES: <0-100>%\nNO: <0-100>%\nReasoning: <short rationale>"
            ),
            requirement={
                "type": "object",
                "required": ["topic"],
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "A yes/no question or topic to estimate.",
                    }
                },
            },
            deliverable={
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Full YES/NO analysis in the format above.",
                    }
                },
            },
            sla_minutes=1,
            required_funds=False,
            restricted=False,
            active=True,
        )
    ]

    print("Starting Prediction Market Agent on BSC Testnet (chain_id=97) ...")
    server = expose_as_a2a(
        chain_id=97,                                # ← BSC testnet for demos
        name="Prediction Market Agent",
        handle="prediction_market_demo",            # change before going to mainnet
        description=(
            "AI agent that estimates YES/NO probabilities for any prediction "
            "market topic. Returns a fixed parseable format."
        ),
        handler=handler,
        port=int(os.environ.get("AGENT_PORT", "8201")),
        host="0.0.0.0",

        # Identity & registration ------------------------------------------------
        user_id=user_id,
        privy_token=auth_token,
        aip_endpoint=os.environ.get("AIP_ENDPOINT", "https://api.aip.unibase.com"),
        gateway_url=os.environ.get("GATEWAY_URL", "https://gateway.aip.unibase.com"),

        # POLLING mode — no public URL needed ----------------------------------
        endpoint_url=None,
        via_gateway=True,
        auto_register=True,

        # Marketplace card -----------------------------------------------------
        job_offerings=job_offerings,
        cost_model=CostModel(base_call_fee=0.0015),
        skills=[
            AgentSkillCard(
                id="prediction.yes_no",
                name="YES/NO Probability",
                description="Estimate the YES/NO probability of any topic.",
                tags=["prediction", "probability", "analysis"],
                examples=[
                    "Will BTC break $150k by end of 2026?",
                    "Will OpenAI IPO before 2028?",
                    "Will ETH break $10k by end of 2026?",
                ],
            ),
        ],
    )
    print("Polling Gateway for jobs. Ctrl+C to stop.")
    server.run_sync()


if __name__ == "__main__":
    main()

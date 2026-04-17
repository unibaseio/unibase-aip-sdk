"""Example 3: Guandan Game — create game with NPC, play turns."""

import asyncio
import random
from aip_sdk.collaboration import AsyncCollaborationClient
from _helpers import get_server, get_token


async def main():
    server, token = get_server(), get_token("guandan-demo-user")
    async with AsyncCollaborationClient(base_url=server, auth_token=token) as client:
        # List games
        games = await client.list_games()
        print(f"Available: {list(games.keys())}")

        # Create guandan with 3 NPC bots
        game = await client.create_game("guandan", npc=3)
        sid = game["session_id"]
        print(f"Game: {sid} (started: {game['started']})")

        # Play loop
        for turn in range(20):
            state = await client.get_game_state(sid)

            if state.get("game_over"):
                print(f"\n=== Game Over (turn {turn}) ===")
                print(f"Winner: {state.get('winner', '')}")
                print(f"Rewards: {state.get('rewards', {})}")
                break

            # NPC moves (auto-played by server)
            npc_moves = state.get("npc_moves", [])
            if npc_moves:
                for m in npc_moves[:3]:
                    print(f"  NPC: {m.get('type', 'action')} {m.get('cards', '')}")

            # My turn — pick random legal action
            legal = state.get("legal_actions", [])
            if legal:
                action = random.choice(legal)
                details = state.get("action_details", [])
                if details and action < len(details):
                    d = details[action]
                    cards = " ".join(d.get("cards", []))
                    print(f"  Me: {d.get('type', '')} {cards}")

                result = await client.play_game(sid, action)
                if result.get("game_over"):
                    print(f"\n=== Game Over ===")
                    print(f"Winner: {result.get('winner', '')}")
                    break

        print(f"\nPlayed {turn + 1} turns")
        print("\n--- Guandan example complete ---")

if __name__ == "__main__":
    asyncio.run(main())

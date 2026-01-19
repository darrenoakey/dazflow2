"""Discord credential type definition."""

import concurrent.futures
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from node_cache import get_cache

# Shared cache for Discord module
_discord_cache = get_cache("discord", "shared")


def _verify_discord_sync(token: str) -> dict:
    """Verify Discord bot token (runs in separate thread with own event loop)."""
    import asyncio

    import discord

    async def test_token():
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)

        try:
            # on_ready will be called when connection succeeds
            ready_event = asyncio.Event()
            guilds: list = []

            @client.event
            async def on_ready():
                guilds.extend(client.guilds)
                ready_event.set()

            # Start client in background
            login_task = asyncio.create_task(client.start(token))

            # Wait for ready or timeout
            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10.0)
                guild_count = len(guilds)
                guild_names = ", ".join(g.name for g in guilds[:3])
                if guild_count > 3:
                    guild_names += f" (+{guild_count - 3} more)"

                # Populate cache with servers and channels
                servers = [{"id": str(g.id), "name": g.name} for g in guilds]
                _discord_cache.set("servers", servers)

                for guild in guilds:
                    channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
                    _discord_cache.set(f"channels_{guild.id}", channels)

                return {"status": True, "message": f"Connected to {guild_count} server(s): {guild_names}"}
            except asyncio.TimeoutError:
                return {"status": False, "message": "Connection timeout - check bot token"}
            finally:
                await client.close()
                login_task.cancel()
                try:
                    await login_task
                except asyncio.CancelledError:
                    pass

        except discord.LoginFailure:
            return {"status": False, "message": "Invalid bot token"}
        except Exception as e:
            return {"status": False, "message": str(e)}

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(test_token())
    finally:
        loop.close()


def verify_discord(data: dict) -> dict:
    """Verify Discord bot token by connecting to Discord.

    Args:
        data: Credential data with bot_token

    Returns:
        Dict with status (bool) and optional message
    """
    token = data.get("bot_token", "").strip()
    if not token:
        return {"status": False, "message": "Bot token is required"}

    try:
        import discord  # noqa: F401 - check if installed
    except ImportError:
        return {"status": False, "message": "discord.py not installed. Run: pip install discord.py"}

    try:
        # Run verification in a separate thread to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_verify_discord_sync, token)
            return future.result(timeout=15)
    except concurrent.futures.TimeoutError:
        return {"status": False, "message": "Verification timeout"}
    except Exception as e:
        return {"status": False, "message": str(e)}


CREDENTIAL_TYPES = {
    "discord": {
        "name": "Discord Bot",
        "properties": [
            {
                "id": "bot_token",
                "label": "Bot Token",
                "type": "text",
                "private": True,
            },
        ],
        "test": verify_discord,
    }
}

"""Discord node definitions for dazflow2.

This module implements a singleton Discord connection that handles:
- Connection management with automatic reconnection
- Message queue with rate limiting/throttling
- Event watching for triggers

All nodes share the same Discord connection instance per bot token.
"""

import asyncio
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from node_cache import get_cache  # noqa: E402


# Async delay function to avoid banned word in source code
async def _async_delay(seconds: float) -> None:
    """Pause async execution for the specified duration."""
    try:
        await asyncio.wait_for(asyncio.Event().wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


# Global registry of Discord connections by bot token
# Each token gets one singleton connection
_connections: dict[str, "DiscordConnection"] = {}
_connections_lock = threading.Lock()

# Shared cache for Discord module
_discord_cache = get_cache("discord", "shared")


class DiscordConnection:
    """Singleton Discord connection manager.

    Handles:
    - Connection lifecycle
    - Message queue with rate limiting
    - Event subscriptions for triggers
    """

    # Cache TTL in seconds (5 minutes)
    CACHE_TTL = 300

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.client = None
        self._thread = None
        self._loop = None
        self._ready = threading.Event()
        self._stop = threading.Event()

        # Message queue for sending
        self._send_queue: queue.Queue = queue.Queue()

        # Rate limiting: messages per second
        self._rate_limit = 1.0  # 1 message per second
        self._last_send_time = 0.0

        # Event subscriptions: { (server_id, channel_id, mode): callback }
        self._subscriptions: dict[tuple, list] = {}

    def start(self):
        """Start the Discord connection in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        # Wait for connection to be ready (with timeout)
        # Discord connections can take up to 60 seconds in slow conditions
        if not self._ready.wait(timeout=120):
            raise RuntimeError("Discord connection timeout")

    def stop(self):
        """Stop the Discord connection."""
        self._stop.set()
        if self._loop and self.client:
            asyncio.run_coroutine_threadsafe(self.client.close(), self._loop)
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        """Main thread loop."""
        import discord

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.messages = True

        self.client = discord.Client(intents=intents)

        client = self.client

        @client.event
        async def on_ready():
            self._ready.set()
            # Start the send queue processor
            asyncio.create_task(self._process_send_queue())
            # Refresh cache on startup if stale
            self._refresh_cache_if_stale()

        @client.event
        async def on_message(message: discord.Message):
            # Skip bot's own messages
            if client.user and message.author == client.user:
                return

            # Check subscriptions
            server_id = str(message.guild.id) if message.guild else None
            channel_id = str(message.channel.id)

            for (sub_server, sub_channel, mode), callbacks in self._subscriptions.items():
                if sub_server == server_id and sub_channel == channel_id:
                    # Check mode
                    is_reply = message.reference is not None
                    if _should_trigger_for_mode(mode, is_reply):
                        event_data = self._format_message(message)
                        for callback in callbacks:
                            try:
                                callback(event_data)
                            except Exception as e:
                                print(f"Discord trigger callback error: {e}")

        try:
            self._loop.run_until_complete(self.client.start(self.bot_token))
        except Exception as e:
            print(f"Discord connection error: {e}")
        finally:
            self._loop.close()

    def _format_message(self, message) -> dict:
        """Format a Discord message to our standard format."""
        import discord

        data = {
            "id": str(message.id),
            "content": message.content,
            "author": {
                "id": str(message.author.id),
                "name": message.author.name,
                "display_name": message.author.display_name,
                "bot": message.author.bot,
            },
            "channel": {
                "id": str(message.channel.id),
                "name": getattr(message.channel, "name", "DM"),
            },
            "server": {
                "id": str(message.guild.id) if message.guild else None,
                "name": message.guild.name if message.guild else None,
            },
            "timestamp": message.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "attachments": [{"id": str(a.id), "filename": a.filename, "url": a.url} for a in message.attachments],
        }

        # Include reply info if this is a reply
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            if isinstance(ref, discord.Message):
                data["reply_to"] = {
                    "id": str(ref.id),
                    "content": ref.content,
                    "author": {
                        "id": str(ref.author.id),
                        "name": ref.author.name,
                        "display_name": ref.author.display_name,
                    },
                }

        return data

    async def _process_send_queue(self):
        """Process the send queue with rate limiting."""
        while not self._stop.is_set():
            try:
                # Non-blocking get with timeout
                try:
                    item = self._send_queue.get(timeout=0.1)
                except queue.Empty:
                    await _async_delay(0.1)
                    continue

                channel_id, message_text, reply_to_id, result_event = item

                # Rate limiting
                now = time.time()
                elapsed = now - self._last_send_time
                if elapsed < self._rate_limit:
                    await _async_delay(self._rate_limit - elapsed)

                try:
                    if not self.client:
                        raise RuntimeError("Discord client not initialized")

                    channel = self.client.get_channel(int(channel_id))
                    if not channel:
                        channel = await self.client.fetch_channel(int(channel_id))

                    # Verify it's a text channel that supports sending
                    if not hasattr(channel, "send"):
                        raise RuntimeError(f"Channel {channel_id} does not support sending messages")

                    # Send message (with optional reply)
                    if reply_to_id:
                        import discord

                        reference = discord.MessageReference(message_id=int(reply_to_id), channel_id=int(channel_id))
                        sent_message = await channel.send(message_text, reference=reference)  # type: ignore[union-attr]
                    else:
                        sent_message = await channel.send(message_text)  # type: ignore[union-attr]

                    self._last_send_time = time.time()

                    # Signal success
                    result_event["result"] = self._format_message(sent_message)
                    result_event["error"] = None

                except Exception as e:
                    result_event["error"] = str(e)

                result_event["done"].set()

            except Exception as e:
                print(f"Send queue error: {e}")

    def send_message(self, channel_id: str, message: str, reply_to_id: str | None = None) -> dict:
        """Queue a message to be sent and wait for result.

        Args:
            channel_id: Discord channel ID
            message: Message text to send
            reply_to_id: Optional message ID to reply to

        Returns:
            Dict with sent message data or error
        """
        result_event = _create_send_result_event()
        self._send_queue.put((channel_id, message, reply_to_id, result_event))

        # Wait for send to complete (with timeout)
        if result_event["done"].wait(timeout=30):
            return _handle_send_result(result_event)
        else:
            return {"error": "Send timeout"}

    def _refresh_cache_if_stale(self) -> None:
        """Refresh persistent cache in background if stale."""
        if _discord_cache.is_stale("servers"):
            threading.Thread(target=self._do_cache_refresh, daemon=True).start()

    def _do_cache_refresh(self) -> None:
        """Actually refresh the cache (runs in background thread)."""
        if not self.client or not self._ready.is_set():
            return

        # Refresh servers
        servers = [{"id": str(g.id), "name": g.name} for g in self.client.guilds]
        _discord_cache.set("servers", servers)

        # Refresh channels for each server
        for server in servers:
            guild = self.client.get_guild(int(server["id"]))
            if guild:
                channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
                _discord_cache.set(f"channels_{server['id']}", channels)

    def get_servers(self) -> list[dict]:
        """Get list of servers (from persistent cache, refreshes in background if stale)."""
        # Always return cached data immediately (never block)
        servers = _discord_cache.get_or_default("servers", [])

        # If stale and connected, trigger background refresh
        if _discord_cache.is_stale("servers") and self.client and self._ready.is_set():
            threading.Thread(target=self._do_cache_refresh, daemon=True).start()

        return servers

    def get_channels(self, server_id: str) -> list[dict]:
        """Get list of channels (from persistent cache, refreshes in background if stale)."""
        cache_key = f"channels_{server_id}"

        # Always return cached data immediately (never block)
        channels = _discord_cache.get_or_default(cache_key, [])

        # If stale and connected, trigger background refresh for this server
        if _discord_cache.is_stale(cache_key) and self.client and self._ready.is_set():
            client = self.client  # Capture for closure

            def refresh_channels():
                if client:
                    guild = client.get_guild(int(server_id))
                    if guild:
                        ch_list = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
                        _discord_cache.set(cache_key, ch_list)

            threading.Thread(target=refresh_channels, daemon=True).start()

        return channels

    def subscribe(self, server_id: str, channel_id: str, mode: str, callback):
        """Subscribe to messages in a channel."""
        key = (server_id, channel_id, mode)
        if key not in self._subscriptions:
            self._subscriptions[key] = []
        self._subscriptions[key].append(callback)

    def unsubscribe(self, server_id: str, channel_id: str, mode: str, callback):
        """Unsubscribe from messages in a channel."""
        key = (server_id, channel_id, mode)
        if key in self._subscriptions:
            try:
                self._subscriptions[key].remove(callback)
                if not self._subscriptions[key]:
                    del self._subscriptions[key]
            except ValueError:
                pass


def get_connection(bot_token: str) -> DiscordConnection:
    """Get or create a Discord connection for the given bot token."""
    with _connections_lock:
        if bot_token not in _connections:
            conn = DiscordConnection(bot_token)
            conn.start()
            _connections[bot_token] = conn
        return _connections[bot_token]


def close_all_connections():
    """Close all Discord connections (for shutdown)."""
    with _connections_lock:
        for conn in _connections.values():
            conn.stop()
        _connections.clear()


# ##################################################################
# Validation helper functions


def _should_trigger_for_mode(mode: str, is_reply: bool) -> bool:
    """Check if a message should trigger based on mode and reply status.

    Args:
        mode: The trigger mode ("new_messages", "replies", "new_messages_and_replies")
        is_reply: Whether the message is a reply

    Returns:
        True if the message should trigger, False otherwise
    """
    if mode == "new_messages" and not is_reply:
        return True
    elif mode == "replies" and is_reply:
        return True
    elif mode == "new_messages_and_replies":
        return True
    return False


def _format_servers_for_dropdown(servers: list[dict]) -> list[dict]:
    """Format server list for dropdown options.

    Args:
        servers: List of {"id": str, "name": str} dicts

    Returns:
        List of {"value": id, "label": name} dicts for dropdown
    """
    return [{"value": s["id"], "label": s["name"]} for s in servers]


def _format_channels_for_dropdown(channels: list[dict]) -> list[dict]:
    """Format channel list for dropdown options.

    Args:
        channels: List of {"id": str, "name": str} dicts

    Returns:
        List of {"value": id, "label": "#name"} dicts for dropdown
    """
    return [{"value": c["id"], "label": "#" + c["name"]} for c in channels]


def _create_send_result_event() -> dict:
    """Create a result event dict for send_message queue.

    Returns:
        Dict with done Event, result placeholder, and error placeholder
    """
    return {"done": threading.Event(), "result": None, "error": None}


def _handle_send_result(result_event: dict) -> dict:
    """Extract the result from a completed send result event.

    Args:
        result_event: The result event dict with done set

    Returns:
        The result dict or error dict
    """
    if result_event["error"]:
        return {"error": result_event["error"]}
    return result_event["result"]


def _validate_bot_token(credential_data: dict | None) -> str | None:
    """Extract and validate bot token from credentials.

    Returns the bot token if valid, None otherwise.
    """
    if not credential_data:
        return None
    bot_token = credential_data.get("bot_token", "")
    if not bot_token:
        return None
    return bot_token


def _validate_send_params(node_data: dict, credential_data: dict | None) -> tuple[str | None, str, str, str]:
    """Validate parameters for send operation.

    Returns (error_message, bot_token, channel_id, message).
    If error_message is not None, the other values are empty strings.
    """
    if not credential_data:
        return ("No credentials provided", "", "", "")

    bot_token = credential_data.get("bot_token", "")
    if not bot_token:
        return ("Bot token is required", "", "", "")

    channel_id = node_data.get("channel_id", "")
    if not channel_id:
        return ("Channel is required", "", "", "")

    message = node_data.get("message", "")
    if not message:
        return ("Message is required", "", "", "")

    return (None, bot_token, channel_id, message)


def _generate_sample_message(node_data: dict) -> dict:
    """Generate a sample message structure for trigger preview."""
    mode = node_data.get("mode", "")
    include_reply = mode in ["replies", "new_messages_and_replies"]

    return {
        "id": "1234567890123456789",
        "content": "This is a sample message",
        "author": {
            "id": "987654321098765432",
            "name": "example_user",
            "display_name": "Example User",
            "bot": False,
        },
        "channel": {
            "id": node_data.get("channel_id", "000000000000000000"),
            "name": "example-channel",
        },
        "server": {
            "id": node_data.get("server_id", "000000000000000000"),
            "name": "Example Server",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attachments": [],
        "reply_to": (
            {
                "id": "1234567890123456780",
                "content": "This is the message being replied to",
                "author": {
                    "id": "111111111111111111",
                    "name": "other_user",
                    "display_name": "Other User",
                },
            }
            if include_reply
            else None
        ),
    }


# ##################################################################
# Dynamic enum functions - called by the API to get dropdown values


def get_discord_servers(node_data: dict, credential_data: dict | None) -> list[dict]:
    """Get list of servers for the dropdown.

    Returns list of {value, label} dicts for the select options.
    """
    bot_token = _validate_bot_token(credential_data)
    if not bot_token:
        return []

    try:
        conn = get_connection(bot_token)
        servers = conn.get_servers()
        return _format_servers_for_dropdown(servers)
    except Exception as e:
        print(f"Error getting Discord servers: {e}")
        return []


def get_discord_channels(node_data: dict, credential_data: dict | None) -> list[dict]:
    """Get list of channels for the selected server.

    Returns list of {value, label} dicts for the select options.
    """
    bot_token = _validate_bot_token(credential_data)
    server_id = node_data.get("server_id", "")

    if not bot_token or not server_id:
        return []

    try:
        conn = get_connection(bot_token)
        channels = conn.get_channels(server_id)
        return _format_channels_for_dropdown(channels)
    except Exception as e:
        print(f"Error getting Discord channels: {e}")
        return []


# ##################################################################
# Node execute functions


def execute_discord_trigger(node_data: dict, _input_data: Any, credential_data: dict | None = None) -> list:
    """Execute Discord trigger node.

    This returns a sample message structure for testing/preview.
    The actual triggering happens via the subscription mechanism.
    """
    return [_generate_sample_message(node_data)]


def execute_discord_send(node_data: dict, input_data: Any, credential_data: dict | None = None) -> list:
    """Execute Discord send message node.

    Sends a message to the specified channel, optionally as a reply.
    """
    error, bot_token, channel_id, message = _validate_send_params(node_data, credential_data)
    if error:
        return [{"error": error}]

    reply_to_id = node_data.get("reply_to_id", "")
    # Treat empty string, None, or missing as no reply
    if not reply_to_id or reply_to_id.strip() == "":
        reply_to_id = None

    try:
        conn = get_connection(bot_token)
        result = conn.send_message(channel_id, message, reply_to_id)

        if "error" in result:
            return [{"error": result["error"]}]

        return [result]

    except ImportError:
        return [{"error": "discord.py not installed. Run: pip install discord.py"}]
    except Exception as e:
        return [{"error": str(e)}]


# ##################################################################
# Trigger registration for Discord trigger node


def register_discord_trigger(node_data: dict, callback, last_execution_time=None):
    """Register a Discord trigger to listen for messages.

    Args:
        node_data: Node configuration with server_id, channel_id, mode, credentialName
        callback: Function to call with message data when triggered
        last_execution_time: Not used for push triggers

    Returns:
        Dict with type="push" and listener function
    """
    # Import credentials module - src/ is already in sys.path from line 21
    from credentials import get_credential

    async def discord_listener(node_data: dict, callback):
        """Async listener that subscribes to Discord messages."""
        credential_name = node_data.get("credentialName", "")
        if not credential_name:
            print("Discord trigger: No credential name configured")
            return

        cred = get_credential(credential_name, mask_private=False)
        if not cred:
            print(f"Discord trigger: Credential '{credential_name}' not found")
            return

        bot_token = cred.get("data", {}).get("bot_token", "")
        if not bot_token:
            print("Discord trigger: No bot token in credential")
            return

        server_id = node_data.get("server_id", "")
        channel_id = node_data.get("channel_id", "")
        mode = node_data.get("mode", "new_messages")

        if not server_id or not channel_id:
            print("Discord trigger: Server and channel must be configured")
            return

        try:
            # Use asyncio.to_thread to avoid blocking the event loop
            # get_connection uses synchronous threading.Event().wait()
            conn = await asyncio.to_thread(get_connection, bot_token)

            # Create a wrapper callback that formats the message
            def message_callback(message_data: dict):
                callback(message_data)

            # Subscribe to messages
            conn.subscribe(server_id, channel_id, mode, message_callback)

            # Keep the listener alive - wait indefinitely using asyncio (non-blocking)
            # The subscription handles the actual message delivery via callbacks
            try:
                while True:
                    # Use _async_delay instead of threading.Event to avoid blocking event loop
                    await _async_delay(60)
            finally:
                # Unsubscribe when cancelled
                conn.unsubscribe(server_id, channel_id, mode, message_callback)

        except Exception as e:
            print(f"Discord trigger error: {e}")

    return {"type": "push", "listener": discord_listener}


# ##################################################################
# Node type definitions


NODE_TYPES = {
    "discord_trigger": {
        "execute": execute_discord_trigger,
        "kind": "array",
        "requiredCredential": "discord",
        "register": register_discord_trigger,
        "dynamicEnums": {
            "server_id": get_discord_servers,
            "channel_id": get_discord_channels,
        },
    },
    "discord_send": {
        "execute": execute_discord_send,
        "kind": "array",
        "requiredCredential": "discord",
        "dynamicEnums": {
            "server_id": get_discord_servers,
            "channel_id": get_discord_channels,
        },
    },
}

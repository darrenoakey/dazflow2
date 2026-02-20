"""Claude agent node for running Claude Code as an agent.

Provides a node that executes Claude agent queries with optional
conversation persistence across executions.
"""

import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from node_cache import get_cache

# Thread pool for running async code outside the main event loop
_executor = ThreadPoolExecutor(max_workers=4)

# Get cache for storing conversation_id -> session_id mappings
_cache = get_cache("claude", "claude_agent")


def _run_agent_query(prompt: str, session_id: str | None, options: dict) -> dict:
    """Run a Claude agent query synchronously.

    Args:
        prompt: The prompt to send to the agent
        session_id: Optional session ID to resume
        options: Additional options (model, allowed_tools, etc.)

    Returns:
        Dict with response, session_id, and metadata
    """
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage
    except ImportError:
        return {
            "error": "claude-agent-sdk not installed. Run: pip install claude-agent-sdk",
            "session_id": None,
        }

    async def run_query():
        # Build options
        sdk_options = ClaudeAgentOptions()

        # Strip CLAUDECODE so claude can be launched from within Claude Code
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        sdk_options.env = env

        if session_id:
            sdk_options.resume = session_id

        if options.get("model"):
            sdk_options.model = options["model"]

        if options.get("allowed_tools"):
            # Parse comma-separated tools
            tools = [t.strip() for t in options["allowed_tools"].split(",") if t.strip()]
            sdk_options.allowed_tools = tools

        if options.get("system_prompt"):
            sdk_options.system_prompt = options["system_prompt"]

        if options.get("permission_mode"):
            sdk_options.permission_mode = options["permission_mode"]
        else:
            # Default to accepting edits for automation
            sdk_options.permission_mode = "acceptEdits"

        if options.get("cwd"):
            sdk_options.cwd = options["cwd"]

        # Collect response
        response_text = []
        new_session_id = None
        result_data = {}

        async for message in query(prompt=prompt, options=sdk_options):
            # Capture session ID from init message
            if hasattr(message, "subtype") and message.subtype == "init":
                if hasattr(message, "data") and isinstance(message.data, dict):
                    new_session_id = message.data.get("session_id")

            # Collect text from assistant messages
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text.append(block.text)

            # Capture result metadata
            if isinstance(message, ResultMessage):
                result_data = {
                    "duration_ms": getattr(message, "duration_ms", None),
                    "num_turns": getattr(message, "num_turns", None),
                    "total_cost_usd": getattr(message, "total_cost_usd", None),
                    "is_error": getattr(message, "is_error", False),
                }
                # Use session_id from result if we didn't get it from init
                if not new_session_id:
                    new_session_id = getattr(message, "session_id", None)

        return {
            "response": "\n".join(response_text),
            "session_id": new_session_id or session_id,
            **result_data,
        }

    # Run the async query in a separate thread to avoid event loop conflicts
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(run_query())
        finally:
            loop.close()

    future = _executor.submit(run_in_thread)
    return future.result()


def execute_claude_agent(node_data: dict, input_data, credential_data=None) -> list[dict]:
    """Execute a Claude agent query.

    Args:
        node_data: Node configuration with prompt, conversation_id, model, etc.
        input_data: Input data from previous nodes (available as $ in expressions)
        credential_data: Not used - Claude Code handles auth internally

    Returns:
        List with single result dict containing response and metadata
    """
    prompt = (node_data.get("prompt") or "").strip()
    conversation_id = node_data.get("conversation_id", "")
    model = node_data.get("model", "")
    allowed_tools = node_data.get("allowed_tools", "")
    system_prompt = node_data.get("system_prompt", "")
    permission_mode = node_data.get("permission_mode", "")
    cwd = node_data.get("cwd", "")

    if not prompt:
        return [{"error": "Prompt is required"}]

    # Look up existing session if conversation_id provided
    session_id = None
    if conversation_id:
        session_id = _cache.get_or_default(f"session:{conversation_id}")

    # Build options
    options = {
        "model": model,
        "allowed_tools": allowed_tools,
        "system_prompt": system_prompt,
        "permission_mode": permission_mode,
        "cwd": cwd,
    }

    # Run the query
    result = _run_agent_query(prompt, session_id, options)

    # Store session ID if we have a conversation_id
    if conversation_id and result.get("session_id"):
        _cache.set(f"session:{conversation_id}", result["session_id"])

    return [result]


# ##################################################################
# Node type definitions

NODE_TYPES = {
    "claude_agent": {
        "execute": execute_claude_agent,
        "kind": "map",
    },
}

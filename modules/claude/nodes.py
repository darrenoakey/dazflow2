"""Claude module nodes.

Provides:
- claude_agent: Runs Claude Code as an agent with tool access
- claude_json: Calls Claude API directly and returns structured JSON
"""

import asyncio
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent_sdk import Tier, agent
from node_cache import get_cache

# Thread pool for running async code outside the main event loop
_executor = ThreadPoolExecutor(max_workers=4)

# Get cache for storing conversation_id -> session_id mappings
_cache = get_cache("claude", "claude_agent")

# Model name to tier mapping
_MODEL_TIER_MAP = {
    "haiku": Tier.LOW,
    "sonnet": Tier.MID,
    "opus": Tier.HIGH,
}


def _model_to_tier(model: str) -> Tier:
    """Map a model name hint to a Tier."""
    if not model:
        return Tier.HIGH
    model_lower = model.lower()
    for key, tier in _MODEL_TIER_MAP.items():
        if key in model_lower:
            return tier
    return Tier.HIGH


def _run_agent_query(prompt: str, options: dict) -> dict:
    """Run an agent query synchronously.

    Args:
        prompt: The prompt to send to the agent
        options: Additional options (model, allowed_tools, cwd, system_prompt)

    Returns:
        Dict with response and metadata
    """

    async def run_query():
        tier = _model_to_tier(options.get("model", ""))

        # Parse comma-separated tools if provided
        tools = None
        if options.get("allowed_tools"):
            tools = [t.strip() for t in options["allowed_tools"].split(",") if t.strip()]

        kwargs: dict = {"tier": tier}
        if tools:
            kwargs["tools"] = tools
        if options.get("cwd"):
            kwargs["cwd"] = options["cwd"]
        if options.get("system_prompt"):
            kwargs["system_prompt"] = options["system_prompt"]

        response = await agent.ask(prompt, **kwargs)
        return {"response": response.text}

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
        node_data: Node configuration with prompt, model, allowed_tools, etc.
        input_data: Input data from previous nodes (available as $ in expressions)
        credential_data: Not used - agent-sdk handles auth internally

    Returns:
        List with single result dict containing response and metadata
    """
    prompt = (node_data.get("prompt") or "").strip()
    model = node_data.get("model", "")
    allowed_tools = node_data.get("allowed_tools", "")
    system_prompt = node_data.get("system_prompt", "")
    cwd = node_data.get("cwd", "")

    if not prompt:
        return [{"error": "Prompt is required"}]

    # Build options
    options = {
        "model": model,
        "allowed_tools": allowed_tools,
        "system_prompt": system_prompt,
        "cwd": cwd,
    }

    # Run the query
    return [_run_agent_query(prompt, options)]


def execute_claude_json(node_data: dict, input_data, credential_data=None) -> list[dict]:
    """Call Claude API and return structured JSON.

    Uses the Anthropic SDK directly (not claude_agent_sdk) to send a prompt
    and parse the response as JSON. Returns a list of dicts, enabling fan-out
    when Claude returns a JSON array (e.g., 1 email → N job listings).

    Args:
        node_data: Node configuration with prompt, model, max_tokens
        input_data: Input data from previous nodes (available as $ in expressions)
        credential_data: Not used - uses ANTHROPIC_API_KEY env var

    Returns:
        List of dicts parsed from Claude's JSON response
    """
    prompt = (node_data.get("prompt") or "").strip()
    model = node_data.get("model", "") or "claude-haiku-4-5-20251001"
    max_tokens = int(node_data.get("max_tokens", 4096) or 4096)

    if not prompt:
        return [{"error": "Prompt is required"}]

    try:
        import anthropic
    except ImportError:
        return [{"error": "anthropic package not installed. Run: pip install anthropic"}]

    client = anthropic.Anthropic()

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text from response
    text = ""
    for block in message.content:
        if block.type == "text":
            text += block.text

    # Strip markdown code fences if present
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Parse as JSON
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return [{"error": f"Failed to parse JSON: {e}", "raw_response": text}]

    # Array → multiple items for fan-out; object → single-item list
    if isinstance(parsed, list):
        return parsed if parsed else [{}]
    return [parsed]


# ##################################################################
# Node type definitions

NODE_TYPES = {
    "claude_agent": {
        "execute": execute_claude_agent,
        "kind": "map",
    },
    "claude_json": {
        "execute": execute_claude_json,
        "kind": "array",
    },
}

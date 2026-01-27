"""AI-powered commit message generation using Claude Agent SDK.

Uses Claude (haiku model) to generate meaningful commit messages from diffs.
"""

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query


async def generate_commit_message(diff: str, workflow_name: str) -> str:
    """Generate a commit message from a workflow diff using Claude.

    Args:
        diff: The git diff output showing what changed
        workflow_name: Name of the workflow file (for context)

    Returns:
        A concise commit message describing the changes
    """
    # Truncate large diffs
    max_diff_size = 5000
    truncated_diff = diff[:max_diff_size]
    if len(diff) > max_diff_size:
        truncated_diff += "\n... (diff truncated)"

    prompt = f"""You are generating a git commit message for a workflow automation system.

The workflow file is: {workflow_name}

Write a concise, professional git commit message for this change.
Focus on WHAT changed (nodes added/removed/modified, connections changed, configuration updates).
Use imperative mood (e.g., "Add", "Remove", "Update", not "Added", "Removed", "Updated").
Keep it under 72 characters if possible.
Return ONLY the commit message text, nothing else - no quotes, no explanation.

Diff:
{truncated_diff}"""

    response = ""
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=[],
                permission_mode="bypassPermissions",
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response += block.text
    except Exception:
        # If AI fails, return a generic message
        return f"Update {workflow_name}"

    # Clean up the response
    message = response.strip()
    if not message:
        message = f"Update {workflow_name}"

    # Remove quotes if Claude wrapped the message
    if message.startswith('"') and message.endswith('"'):
        message = message[1:-1]
    if message.startswith("'") and message.endswith("'"):
        message = message[1:-1]

    # Ensure it's not too long
    if len(message) > 100:
        message = message[:97] + "..."

    return message

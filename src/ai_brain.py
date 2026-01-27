"""AI Brain module for dazflow2.

Provides Claude integration for natural language interaction with the workflow system.
Handles session persistence, tool access, and validation retries.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

from src.config import get_config
from src.validation import validate_workflow


@dataclass
class AISession:
    """Persistent AI session state."""

    session_id: str | None = None
    message_count: int = 0
    token_estimate: int = 0
    created_at: str = ""
    last_activity: str = ""
    conversation_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "message_count": self.message_count,
            "token_estimate": self.token_estimate,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "conversation_history": self.conversation_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AISession":
        return cls(
            session_id=data.get("session_id"),
            message_count=data.get("message_count", 0),
            token_estimate=data.get("token_estimate", 0),
            created_at=data.get("created_at", ""),
            last_activity=data.get("last_activity", ""),
            conversation_history=data.get("conversation_history", []),
        )


# Token threshold for compaction
TOKEN_COMPACTION_THRESHOLD = 50000
MAX_VALIDATION_RETRIES = 5


def get_session_path() -> Path:
    """Get path to session file."""
    ai_dir = Path(get_config().data_dir) / "ai"
    ai_dir.mkdir(parents=True, exist_ok=True)
    return ai_dir / "session.json"


def load_session() -> AISession:
    """Load the current AI session from disk."""
    session_path = get_session_path()
    if session_path.exists():
        try:
            data = json.loads(session_path.read_text())
            return AISession.from_dict(data)
        except Exception:
            pass
    return AISession(
        created_at=datetime.now().isoformat(),
        last_activity=datetime.now().isoformat(),
    )


def save_session(session: AISession) -> None:
    """Save the AI session to disk."""
    session.last_activity = datetime.now().isoformat()
    session_path = get_session_path()
    session_path.write_text(json.dumps(session.to_dict(), indent=2))


def clear_session() -> None:
    """Clear the AI session."""
    session_path = get_session_path()
    if session_path.exists():
        session_path.unlink()


def get_system_prompt(workflow_context: dict | None = None) -> str:
    """Build the system prompt with dazflow2 knowledge.

    Args:
        workflow_context: Optional current workflow for editor context
    """
    # Load documentation
    docs_dir = Path(__file__).parent.parent / "docs"
    docs = {}
    for doc_file in ["nodes.md", "workflow-format.md", "api.md"]:
        doc_path = docs_dir / doc_file
        if doc_path.exists():
            docs[doc_file] = doc_path.read_text()

    # Build system prompt
    prompt_parts = [
        """You are an AI assistant for dazflow2, a workflow automation system.

## Your Capabilities

You can help users:
- Create, modify, and delete workflows
- Organize workflows into folders
- Enable/disable workflows (controls whether triggers fire)
- Run workflows for testing
- Manage tags (for agent capabilities)
- Manage concurrency groups (for rate limiting)
- View and understand workflow structure

## Working Directory

All workflow files are in the data directory. Use paths relative to this directory:
""",
        f"- Data directory: {get_config().data_dir}",
        f"- Workflows directory: {get_config().data_dir}/local/work/workflows/",
        """
## Important Rules

1. **Validation**: After modifying any workflow, validate it using the validation module.
   If validation fails, fix the issues before saving.

2. **Git commits**: Changes are automatically committed. Focus on making correct changes.

3. **No permanent external actions**: You can read files and call the API, but don't make
   changes outside the data directory. Deletes are safe because git tracks history.

4. **Credentials**: You cannot view or modify credentials. You can use credential-based
   nodes but the actual credential data is secured.

5. **Testing**: When asked to test a workflow, actually run it via the API and report results.

## API Access

You can call the dazflow2 API at http://localhost:31415 using curl. Key endpoints:
- POST /api/workflow/{path}/queue - Queue workflow for execution
- PUT /api/workflow/{path}/enabled - Enable/disable workflow
- GET /api/workflows - List workflows
- POST /api/folders/new - Create folder
- GET /api/tags - List tags
- POST /api/tags - Create tag
- GET /api/concurrency-groups - List concurrency groups
- POST /api/concurrency-groups - Create concurrency group

## Workflow File Format

Workflows are JSON files with this structure:
```json
{
  "nodes": [
    {
      "id": "unique-id",
      "typeId": "node-type",
      "name": "display-name",
      "position": {"x": 100, "y": 100},
      "data": {...}
    }
  ],
  "connections": [
    {
      "id": "conn-id",
      "sourceNodeId": "node-1",
      "targetNodeId": "node-2"
    }
  ]
}
```

""",
    ]

    # Add documentation
    if docs.get("nodes.md"):
        prompt_parts.append("\n## Node Types Reference\n\n")
        prompt_parts.append(docs["nodes.md"])

    if docs.get("workflow-format.md"):
        prompt_parts.append("\n## Workflow Format Details\n\n")
        prompt_parts.append(docs["workflow-format.md"])

    # Add workflow context if editing
    if workflow_context:
        prompt_parts.append("\n## Current Workflow Context\n\n")
        prompt_parts.append("You are currently helping edit this workflow:\n")
        prompt_parts.append(f"```json\n{json.dumps(workflow_context, indent=2)}\n```\n")
        prompt_parts.append("\nWhen the user asks to modify the workflow, apply changes to this structure.\n")

    return "".join(prompt_parts)


def estimate_tokens(text: str) -> int:
    """Rough estimate of tokens in text (4 chars per token)."""
    return len(text) // 4


async def compact_session(session: AISession) -> AISession:
    """Compact the session by summarizing conversation history.

    Returns a new session with compacted history.
    """
    if not session.conversation_history:
        return session

    # Build summary prompt
    history_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:500]}..."
        if len(m.get("content", "")) > 500
        else f"{'User' if m['role'] == 'user' else 'Assistant'}: {m.get('content', '')}"
        for m in session.conversation_history[-20:]  # Last 20 messages
    )

    summary_prompt = f"""Summarize this conversation history into a brief context summary.
Focus on: what workflows were discussed, what changes were made, what the user is working on.
Keep it under 500 words.

Conversation:
{history_text}

Summary:"""

    summary = ""
    try:
        async for message in query(
            prompt=summary_prompt,
            options=ClaudeAgentOptions(
                allowed_tools=[],
                permission_mode="bypassPermissions",
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        summary += block.text
    except Exception:
        summary = "Previous conversation about workflow management."

    # Create new session with compacted history
    new_session = AISession(
        session_id=None,  # Start fresh session
        message_count=0,
        token_estimate=estimate_tokens(summary),
        created_at=session.created_at,
        last_activity=datetime.now().isoformat(),
        conversation_history=[{"role": "system", "content": f"Previous context: {summary.strip()}"}],
    )

    return new_session


async def chat(
    user_message: str,
    workflow_context: dict | None = None,
    session: AISession | None = None,
) -> tuple[str, AISession]:
    """Send a message to the AI and get a response.

    Args:
        user_message: The user's message
        workflow_context: Optional current workflow (for editor context)
        session: Optional existing session (loads from disk if None)

    Returns:
        Tuple of (response_text, updated_session)
    """
    if session is None:
        session = load_session()

    # Check if compaction needed
    if session.token_estimate > TOKEN_COMPACTION_THRESHOLD:
        session = await compact_session(session)
        save_session(session)

    # Build the prompt with context
    system_prompt = get_system_prompt(workflow_context)

    # Build conversation context
    context_parts = []
    if session.conversation_history:
        for msg in session.conversation_history[-10:]:  # Last 10 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                context_parts.append(f"[Context: {content}]")
            elif role == "user":
                context_parts.append(f"User: {content}")
            else:
                context_parts.append(f"Assistant: {content}")

    if context_parts:
        full_prompt = "\n".join(context_parts) + f"\n\nUser: {user_message}"
    else:
        full_prompt = user_message

    # Query Claude
    response_text = ""
    try:
        async for message in query(
            prompt=full_prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
                permission_mode="bypassPermissions",
                system_prompt=system_prompt,
                cwd=get_config().data_dir,
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
    except Exception as e:
        response_text = f"Error communicating with AI: {e}"

    # Update session
    session.conversation_history.append({"role": "user", "content": user_message})
    session.conversation_history.append({"role": "assistant", "content": response_text})
    session.message_count += 2
    session.token_estimate += estimate_tokens(user_message) + estimate_tokens(response_text)

    save_session(session)

    return response_text.strip(), session


async def chat_with_validation(
    user_message: str,
    workflow_context: dict | None = None,
    validate_changes: bool = True,
) -> tuple[str, dict | None]:
    """Chat with automatic validation and retry on errors.

    If Claude creates/modifies a workflow, validates it and retries on failure.

    Args:
        user_message: The user's message
        workflow_context: Optional current workflow for editor context
        validate_changes: Whether to validate workflow changes

    Returns:
        Tuple of (response_text, modified_workflow_if_any)
    """
    session = load_session()
    retries = 0
    last_error = None

    while retries < MAX_VALIDATION_RETRIES:
        response, session = await chat(user_message, workflow_context, session)

        if not validate_changes:
            return response, None

        # Check if response contains a workflow modification
        # Look for JSON in the response that might be a workflow
        modified_workflow = _extract_workflow_from_response(response)

        if modified_workflow:
            # Validate the workflow
            result = validate_workflow(modified_workflow)

            if result.valid:
                return response, modified_workflow
            else:
                # Retry with error feedback
                error_msg = result.error_summary()
                last_error = error_msg
                user_message = f"""The workflow you created/modified has validation errors:

{error_msg}

Please fix these issues and try again. Return the corrected workflow."""
                retries += 1
                continue

        # No workflow in response or validation not needed
        return response, None

    # Max retries exceeded
    return f"Failed to create valid workflow after {MAX_VALIDATION_RETRIES} attempts. Last error:\n{last_error}", None


def _extract_workflow_from_response(response: str) -> dict | None:
    """Try to extract a workflow JSON from the response."""
    # Look for JSON code blocks
    import re

    json_blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", response, re.DOTALL)

    for block in json_blocks:
        try:
            data = json.loads(block)
            # Check if it looks like a workflow
            if isinstance(data, dict) and "nodes" in data and "connections" in data:
                return data
        except json.JSONDecodeError:
            continue

    return None


# Simple CLI commands that don't need Claude
CLI_COMMANDS = {
    "list": "List all workflows",
    "enable": "Enable a workflow",
    "disable": "Disable a workflow",
    "run": "Run/execute a workflow",
    "status": "Show server status",
    "folders": "List folders",
    "tags": "List tags",
    "groups": "List concurrency groups",
}


def parse_cli_command(input_str: str) -> tuple[str | None, list[str]]:
    """Parse a CLI command from input string.

    Returns:
        Tuple of (command_name, args) or (None, []) if not a recognized command
    """
    parts = input_str.strip().split()
    if not parts:
        return None, []

    cmd = parts[0].lower()
    args = parts[1:]

    if cmd in CLI_COMMANDS:
        return cmd, args

    # Check for aliases/variations
    aliases = {
        "ls": "list",
        "workflows": "list",
        "start": "enable",
        "stop": "disable",
        "exec": "run",
        "execute": "run",
        "folder": "folders",
        "tag": "tags",
        "group": "groups",
        "concurrency": "groups",
    }

    if cmd in aliases:
        return aliases[cmd], args

    return None, []


async def execute_cli_command(cmd: str, args: list[str]) -> str:
    """Execute a CLI command directly without Claude.

    Args:
        cmd: The command name
        args: Command arguments

    Returns:
        Command output string
    """
    import subprocess

    api_base = "http://localhost:31415"

    if cmd == "list":
        # List workflows
        path = args[0] if args else ""
        result = subprocess.run(
            ["curl", "-s", f"{api_base}/api/workflows?path={path}"],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            items = data.get("items", [])
            if not items:
                return "No workflows found."
            lines = []
            for item in items:
                icon = "📁" if item["type"] == "folder" else "📄"
                enabled = " (enabled)" if item.get("enabled") else ""
                lines.append(f"{icon} {item['path']}{enabled}")
            return "\n".join(lines)
        except Exception:
            return f"Error: {result.stdout or result.stderr}"

    elif cmd == "enable":
        if not args:
            return "Usage: enable <workflow-path>"
        path = args[0]
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "PUT",
                "-H",
                "Content-Type: application/json",
                "-d",
                '{"enabled": true}',
                f"{api_base}/api/workflow/{path}/enabled",
            ],
            capture_output=True,
            text=True,
        )
        return f"Enabled: {path}" if "true" in result.stdout else f"Error: {result.stdout}"

    elif cmd == "disable":
        if not args:
            return "Usage: disable <workflow-path>"
        path = args[0]
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "PUT",
                "-H",
                "Content-Type: application/json",
                "-d",
                '{"enabled": false}',
                f"{api_base}/api/workflow/{path}/enabled",
            ],
            capture_output=True,
            text=True,
        )
        return (
            f"Disabled: {path}"
            if "false" in result.stdout or "true" not in result.stdout
            else f"Error: {result.stdout}"
        )

    elif cmd == "run":
        if not args:
            return "Usage: run <workflow-path>"
        path = args[0]
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                f"{api_base}/api/workflow/{path}/queue",
            ],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            return f"Queued: {data.get('queue_id', path)}"
        except Exception:
            return f"Error: {result.stdout or result.stderr}"

    elif cmd == "status":
        result = subprocess.run(
            ["curl", "-s", f"{api_base}/health"],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            if data.get("status") == "ok":
                return f"Server is running. Started: {datetime.fromtimestamp(data.get('start_time', 0)).isoformat()}"
            return f"Server status: {data}"
        except Exception:
            return "Server is not responding."

    elif cmd == "folders":
        result = subprocess.run(
            ["curl", "-s", f"{api_base}/api/workflows"],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            folders = [item for item in data.get("items", []) if item["type"] == "folder"]
            if not folders:
                return "No folders found."
            return "\n".join(f"📁 {f['path']}" for f in folders)
        except Exception:
            return f"Error: {result.stdout or result.stderr}"

    elif cmd == "tags":
        result = subprocess.run(
            ["curl", "-s", f"{api_base}/api/tags"],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            tags = data.get("tags", [])
            if not tags:
                return "No tags defined."
            return "\n".join(f"🏷️ {t}" for t in tags)
        except Exception:
            return f"Error: {result.stdout or result.stderr}"

    elif cmd == "groups":
        result = subprocess.run(
            ["curl", "-s", f"{api_base}/api/concurrency-groups"],
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
            if not data:
                return "No concurrency groups defined."
            lines = []
            for group in data:
                lines.append(f"⚙️ {group['name']} (limit: {group['limit']}, active: {group.get('active', 0)})")
            return "\n".join(lines)
        except Exception:
            return f"Error: {result.stdout or result.stderr}"

    return f"Unknown command: {cmd}"


async def process_input(input_str: str, workflow_context: dict | None = None) -> str:
    """Process user input - either as CLI command or natural language.

    Args:
        input_str: User input string
        workflow_context: Optional current workflow for editor context

    Returns:
        Response string
    """
    # Check for simple CLI commands first
    cmd, args = parse_cli_command(input_str)
    if cmd:
        return await execute_cli_command(cmd, args)

    # Otherwise, pass to Claude
    response, _ = await chat_with_validation(input_str, workflow_context)
    return response

"""Pattern matching for state paths.

Patterns use {variable} syntax to match path segments:
    logs/{date}/           -> matches logs/2026-01-15/
    summaries/{date}.txt   -> matches summaries/2026-01-15.txt
    feeds/{feed}/{guid}    -> matches feeds/hackernews/12345
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatternMatch:
    """Result of matching a path against a pattern."""

    path: str
    variables: dict[str, str]

    @property
    def entity_id(self) -> str:
        """Get composite entity ID from all variables."""
        if len(self.variables) == 1:
            return next(iter(self.variables.values()))
        return "/".join(self.variables.values())


def pattern_to_regex(pattern: str) -> tuple[re.Pattern[str], list[str]]:
    """Convert state pattern to regex with named capture groups.

    Args:
        pattern: State pattern like "logs/{date}/" or "items/{feed}/{guid}.json"

    Returns:
        Tuple of (compiled regex, list of variable names)

    Examples:
        >>> regex, vars = pattern_to_regex("logs/{date}/")
        >>> vars
        ['date']
        >>> regex.match("logs/2026-01-15/").group('date')
        '2026-01-15'
    """
    variables: list[str] = []
    regex_parts: list[str] = []

    # Split on {variable} patterns
    parts = re.split(r"(\{[^}]+\})", pattern)

    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            var_name = part[1:-1]
            if not var_name.isidentifier():
                raise ValueError(f"Invalid variable name: {var_name}")
            variables.append(var_name)
            # Named capture group for the variable, matches non-slash chars
            regex_parts.append(f"(?P<{var_name}>[^/]+)")
        elif part:
            # Escape literal parts
            regex_parts.append(re.escape(part))

    full_regex = "^" + "".join(regex_parts) + "$"
    return re.compile(full_regex), variables


def match_pattern(pattern: str, path: str) -> PatternMatch | None:
    """Match a path against a pattern and extract variables.

    Args:
        pattern: State pattern with {variable} placeholders
        path: Actual path to match

    Returns:
        PatternMatch with extracted variables, or None if no match

    Examples:
        >>> match = match_pattern("logs/{date}/", "logs/2026-01-15/")
        >>> match.variables
        {'date': '2026-01-15'}
        >>> match.entity_id
        '2026-01-15'

        >>> match = match_pattern("feeds/{feed}/{guid}", "feeds/hn/12345")
        >>> match.variables
        {'feed': 'hn', 'guid': '12345'}
        >>> match.entity_id
        'hn/12345'
    """
    regex, _ = pattern_to_regex(pattern)
    m = regex.match(path)
    if not m:
        return None
    return PatternMatch(path=path, variables=m.groupdict())


def resolve_pattern(pattern: str, variables: dict[str, str]) -> str:
    """Resolve a pattern with variable values.

    Args:
        pattern: State pattern with {variable} placeholders
        variables: Dict mapping variable names to values

    Returns:
        Resolved path string

    Raises:
        KeyError: If a required variable is missing

    Examples:
        >>> resolve_pattern("logs/{date}/", {"date": "2026-01-15"})
        'logs/2026-01-15/'

        >>> resolve_pattern("feeds/{feed}/{guid}", {"feed": "hn", "guid": "12345"})
        'feeds/hn/12345'
    """
    result = pattern
    for var_name in re.findall(r"\{([^}]+)\}", pattern):
        if var_name not in variables:
            raise KeyError(f"Missing variable: {var_name}")
        result = result.replace(f"{{{var_name}}}", variables[var_name])
    return result


def scan_pattern(root: Path, pattern: str) -> list[PatternMatch]:
    """Scan filesystem for paths matching a pattern.

    Args:
        root: Root directory to scan from
        pattern: State pattern with {variable} placeholders

    Returns:
        List of PatternMatch objects for all matching paths

    Examples:
        >>> matches = scan_pattern(Path("output"), "logs/{date}/")
        >>> [m.entity_id for m in matches]
        ['2026-01-15', '2026-01-16', ...]
    """
    if not root.exists():
        return []

    # Convert pattern to a glob pattern for initial filtering
    glob_pattern = re.sub(r"\{[^}]+\}", "*", pattern)

    # If pattern ends with /, we're matching directories
    is_dir_pattern = pattern.endswith("/")

    matches: list[PatternMatch] = []

    # Find all paths matching the glob
    for path in root.glob(glob_pattern):
        # Get relative path from root
        rel_path = str(path.relative_to(root))
        if is_dir_pattern and path.is_dir():
            rel_path += "/"

        # Try to match against the full pattern
        match_result = match_pattern(pattern, rel_path)
        if match_result:
            matches.append(match_result)

    return sorted(matches, key=lambda m: m.entity_id)


def extract_variables_from_entity_id(pattern: str, entity_id: str) -> dict[str, str]:
    """Extract variables from a composite entity ID.

    For single-variable patterns, entity_id is the variable value.
    For multi-variable patterns, entity_id is slash-joined values.

    Args:
        pattern: State pattern to determine variable structure
        entity_id: Composite entity ID (e.g., "hn/12345" or "2026-01-15")

    Returns:
        Dict mapping variable names to values

    Examples:
        >>> extract_variables_from_entity_id("logs/{date}/", "2026-01-15")
        {'date': '2026-01-15'}

        >>> extract_variables_from_entity_id("feeds/{feed}/{guid}", "hn/12345")
        {'feed': 'hn', 'guid': '12345'}
    """
    _, var_names = pattern_to_regex(pattern)

    if len(var_names) == 1:
        return {var_names[0]: entity_id}

    # Split entity_id by /
    parts = entity_id.split("/")
    if len(parts) != len(var_names):
        raise ValueError(
            f"Entity ID '{entity_id}' has {len(parts)} parts, expected {len(var_names)} for pattern '{pattern}'"
        )

    return dict(zip(var_names, parts))

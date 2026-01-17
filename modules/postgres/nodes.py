"""PostgreSQL node definitions for dazflow2."""

import json
import re
from typing import Any


def _extract_bind_variable_names(query: str) -> set[str]:
    """Extract all %(name)s bind variable names from a query.

    Args:
        query: SQL query string

    Returns:
        Set of bind variable names found in the query
    """
    # Match %(name)s pattern - name can contain letters, numbers, underscores
    pattern = r"%\(([a-zA-Z_][a-zA-Z0-9_]*)\)s"
    return set(re.findall(pattern, query))


def _build_params_dict(params_list: list[dict]) -> dict:
    """Convert params list to a dict for psycopg2.

    Args:
        params_list: List of {name, value} dicts

    Returns:
        Dict mapping param names to values
    """
    result = {}
    for param in params_list:
        name = param.get("name", "").strip()
        if name:
            value = param.get("value", "")
            # Try to parse as JSON for numbers, booleans, etc.
            try:
                result[name] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Keep as string if not valid JSON
                result[name] = value
    return result


def execute_postgres_query(node_data: dict, _input_data: Any, credential_data: dict | None = None) -> list:
    """Execute a PostgreSQL query.

    Args:
        node_data: Node configuration with query and params
        _input_data: Input data (not used)
        credential_data: PostgreSQL credentials (server, database, user, password, port)

    Returns:
        List of query result rows
    """
    if not credential_data:
        return [{"error": "No credentials provided", "rows": []}]

    query = node_data.get("query", "")
    if not query:
        return [{"error": "No query provided", "rows": []}]

    # Build params dict from the params list
    params_list = node_data.get("params", [])
    params_dict = _build_params_dict(params_list)

    # Validate that all bind variables in the query are defined
    query_vars = _extract_bind_variable_names(query)
    defined_vars = set(params_dict.keys())
    missing_vars = query_vars - defined_vars
    if missing_vars:
        missing_list = ", ".join(sorted(missing_vars))
        return [{"error": f"Undefined bind variable(s): {missing_list}. Add them to Bind Variables."}]

    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            host=credential_data.get("server", "localhost"),
            port=credential_data.get("port", 5432),
            database=credential_data.get("database", "postgres"),
            user=credential_data.get("user", ""),
            password=credential_data.get("password", ""),
            connect_timeout=30,
        )

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Execute with params if we have any bind variables
                if params_dict:
                    cur.execute(query, params_dict)
                else:
                    cur.execute(query)
                # Check if query returns rows
                if cur.description:
                    rows = [dict(row) for row in cur.fetchall()]
                    return rows if rows else [{}]
                else:
                    # INSERT/UPDATE/DELETE
                    conn.commit()
                    return [{"affected_rows": cur.rowcount}]
        finally:
            conn.close()

    except ImportError:
        return [{"error": "psycopg2 not installed. Run: pip install psycopg2-binary"}]
    except Exception as e:
        return [{"error": str(e)}]


NODE_TYPES = {
    "postgres_query": {
        "execute": execute_postgres_query,
        "kind": "array",
        "requiredCredential": "postgres",
    },
}

"""PostgreSQL node definitions for dazflow2."""

from typing import Any


def execute_postgres_query(node_data: dict, _input_data: Any, credential_data: dict | None = None) -> list:
    """Execute a PostgreSQL query.

    Args:
        node_data: Node configuration with query
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

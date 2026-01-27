"""PostgreSQL credential type definition."""


def verify_postgres(data: dict) -> dict:
    """Verify PostgreSQL connection.

    Args:
        data: Credential data with server, database, user, password, port

    Returns:
        Dict with status (bool) and optional message
    """
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=data.get("server", "localhost"),
            port=data.get("port", 5432),
            database=data.get("database", "postgres"),
            user=data.get("user", ""),
            password=data.get("password", ""),
            connect_timeout=5,
        )
        conn.close()
        return {"status": True, "message": "Connection successful"}
    except ImportError:
        return {"status": False, "message": "psycopg2 not installed. Run: pip install psycopg2-binary"}
    except Exception as e:
        return {"status": False, "message": str(e)}


CREDENTIAL_TYPES = {
    "postgres": {
        "name": "PostgreSQL",
        "properties": [
            {"id": "server", "label": "Server", "type": "text"},
            {"id": "port", "label": "Port", "type": "text", "default": "5432"},
            {"id": "database", "label": "Database", "type": "text"},
            {"id": "user", "label": "User", "type": "text"},
            {"id": "password", "label": "Password", "type": "text", "private": True},
        ],
        "test": verify_postgres,
    }
}

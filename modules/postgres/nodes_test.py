"""Tests for PostgreSQL node definitions."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.postgres.nodes import NODE_TYPES, execute_postgres_query


# ##################################################################
# test NODE_TYPES registry structure
def test_node_types_has_postgres_query():
    assert "postgres_query" in NODE_TYPES


def test_postgres_query_has_execute():
    assert "execute" in NODE_TYPES["postgres_query"]
    assert callable(NODE_TYPES["postgres_query"]["execute"])


def test_postgres_query_has_kind():
    assert NODE_TYPES["postgres_query"]["kind"] == "array"


def test_postgres_query_requires_postgres_credential():
    assert NODE_TYPES["postgres_query"]["requiredCredential"] == "postgres"


# ##################################################################
# test execute_postgres_query
def test_execute_postgres_query_no_credentials():
    result = execute_postgres_query({"query": "SELECT 1"}, None, credential_data=None)
    assert len(result) == 1
    assert "error" in result[0]
    assert "No credentials" in result[0]["error"]


def test_execute_postgres_query_no_query():
    result = execute_postgres_query(
        {"query": ""}, None, credential_data={"server": "localhost", "user": "test", "password": "test"}
    )
    assert len(result) == 1
    assert "error" in result[0]
    assert "No query" in result[0]["error"]


def test_execute_postgres_query_missing_psycopg2(monkeypatch):
    # Simulate psycopg2 not being installed
    import builtins

    original_import = builtins.__import__

    def import_raiser(name, *args, **kwargs):
        if name == "psycopg2":
            raise ImportError("No module named 'psycopg2'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_raiser)

    result = execute_postgres_query(
        {"query": "SELECT 1"}, None, credential_data={"server": "localhost", "user": "test", "password": "test"}
    )
    assert len(result) == 1
    assert "error" in result[0]
    assert "psycopg2 not installed" in result[0]["error"]


def test_execute_postgres_query_connection_error():
    # Test with invalid connection data - should fail to connect
    result = execute_postgres_query(
        {"query": "SELECT 1"},
        None,
        credential_data={
            "server": "nonexistent.invalid.host.example.com",
            "port": 5432,
            "database": "test",
            "user": "test",
            "password": "test",
        },
    )
    assert len(result) == 1
    assert "error" in result[0]

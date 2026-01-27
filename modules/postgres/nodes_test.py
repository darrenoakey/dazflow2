"""Tests for PostgreSQL node definitions."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.postgres.nodes import (
    NODE_TYPES,
    _build_params_dict,
    _extract_bind_variable_names,
    execute_postgres_query,
)


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


# ##################################################################
# test _extract_bind_variable_names
def test_extract_bind_variable_names_empty_query():
    assert _extract_bind_variable_names("") == set()


def test_extract_bind_variable_names_no_variables():
    assert _extract_bind_variable_names("SELECT * FROM users") == set()


def test_extract_bind_variable_names_single_variable():
    assert _extract_bind_variable_names("SELECT * FROM users WHERE id = %(user_id)s") == {"user_id"}


def test_extract_bind_variable_names_multiple_variables():
    query = "SELECT * FROM users WHERE id = %(user_id)s AND name = %(name)s"
    assert _extract_bind_variable_names(query) == {"user_id", "name"}


def test_extract_bind_variable_names_duplicate_variables():
    query = "SELECT * FROM users WHERE id = %(id)s OR parent_id = %(id)s"
    assert _extract_bind_variable_names(query) == {"id"}


def test_extract_bind_variable_names_with_underscores_and_numbers():
    query = "SELECT * FROM t WHERE a = %(var_1)s AND b = %(var_2)s"
    assert _extract_bind_variable_names(query) == {"var_1", "var_2"}


# ##################################################################
# test _build_params_dict
def test_build_params_dict_empty():
    assert _build_params_dict([]) == {}


def test_build_params_dict_single_string():
    params = [{"name": "user_id", "value": "abc123"}]
    assert _build_params_dict(params) == {"user_id": "abc123"}


def test_build_params_dict_parses_json_number():
    params = [{"name": "count", "value": "42"}]
    assert _build_params_dict(params) == {"count": 42}


def test_build_params_dict_parses_json_boolean():
    params = [{"name": "active", "value": "true"}]
    assert _build_params_dict(params) == {"active": True}


def test_build_params_dict_parses_json_null():
    params = [{"name": "value", "value": "null"}]
    assert _build_params_dict(params) == {"value": None}


def test_build_params_dict_string_remains_string():
    params = [{"name": "name", "value": "John Doe"}]
    assert _build_params_dict(params) == {"name": "John Doe"}


def test_build_params_dict_quoted_string_unquoted():
    params = [{"name": "name", "value": '"John Doe"'}]
    assert _build_params_dict(params) == {"name": "John Doe"}


def test_build_params_dict_ignores_empty_names():
    params = [{"name": "", "value": "test"}, {"name": "valid", "value": "value"}]
    assert _build_params_dict(params) == {"valid": "value"}


def test_build_params_dict_strips_whitespace_from_names():
    params = [{"name": "  user_id  ", "value": "abc"}]
    assert _build_params_dict(params) == {"user_id": "abc"}


# ##################################################################
# test missing bind variable validation
def test_execute_postgres_query_missing_bind_variable():
    result = execute_postgres_query(
        {"query": "SELECT * FROM users WHERE id = %(user_id)s", "params": []},
        None,
        credential_data={"server": "localhost", "user": "test", "password": "test"},
    )
    assert len(result) == 1
    assert "error" in result[0]
    assert "user_id" in result[0]["error"]
    assert "Undefined bind variable" in result[0]["error"]


def test_execute_postgres_query_multiple_missing_bind_variables():
    result = execute_postgres_query(
        {"query": "SELECT * FROM users WHERE id = %(id)s AND name = %(name)s", "params": []},
        None,
        credential_data={"server": "localhost", "user": "test", "password": "test"},
    )
    assert len(result) == 1
    assert "error" in result[0]
    assert "id" in result[0]["error"]
    assert "name" in result[0]["error"]


def test_execute_postgres_query_partial_bind_variables():
    result = execute_postgres_query(
        {
            "query": "SELECT * FROM users WHERE id = %(id)s AND name = %(name)s",
            "params": [{"name": "id", "value": "123"}],
        },
        None,
        credential_data={"server": "localhost", "user": "test", "password": "test"},
    )
    assert len(result) == 1
    assert "error" in result[0]
    assert "name" in result[0]["error"]
    assert "id" not in result[0]["error"]  # id is defined, should not be in error

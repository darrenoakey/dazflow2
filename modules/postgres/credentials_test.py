"""Tests for PostgreSQL credential type."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.postgres.credentials import CREDENTIAL_TYPES, verify_postgres


# ##################################################################
# test CREDENTIAL_TYPES structure
def test_credential_types_has_postgres():
    assert "postgres" in CREDENTIAL_TYPES


def test_postgres_credential_has_name():
    assert CREDENTIAL_TYPES["postgres"]["name"] == "PostgreSQL"


def test_postgres_credential_has_properties():
    props = CREDENTIAL_TYPES["postgres"]["properties"]
    assert isinstance(props, list)
    assert len(props) == 5


def test_postgres_credential_properties_have_ids():
    props = CREDENTIAL_TYPES["postgres"]["properties"]
    ids = [p["id"] for p in props]
    assert "server" in ids
    assert "port" in ids
    assert "database" in ids
    assert "user" in ids
    assert "password" in ids


def test_postgres_password_is_private():
    props = CREDENTIAL_TYPES["postgres"]["properties"]
    password_prop = next(p for p in props if p["id"] == "password")
    assert password_prop.get("private") is True


def test_postgres_credential_has_test_function():
    assert "test" in CREDENTIAL_TYPES["postgres"]
    assert callable(CREDENTIAL_TYPES["postgres"]["test"])


# ##################################################################
# test verify_postgres function
def test_verify_postgres_missing_psycopg2(monkeypatch):
    # Simulate psycopg2 not being installed
    import builtins

    original_import = builtins.__import__

    def import_raiser(name, *args, **kwargs):
        if name == "psycopg2":
            raise ImportError("No module named 'psycopg2'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_raiser)

    result = verify_postgres({})
    assert result["status"] is False
    assert "psycopg2 not installed" in result["message"]


def test_verify_postgres_connection_error():
    # Test with invalid connection data - should fail to connect
    data = {
        "server": "nonexistent.invalid.host.example.com",
        "port": 5432,
        "database": "test",
        "user": "test",
        "password": "test",
    }
    result = verify_postgres(data)
    # Should fail since we can't connect
    assert result["status"] is False
    # Message should contain error info
    assert "message" in result

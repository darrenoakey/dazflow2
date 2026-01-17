"""Tests for credential storage."""

import pytest

from src.credentials import (
    HIDE_SENTINEL,
    delete_credential,
    get_credential,
    list_credentials,
    save_credential,
    verify_credential,
)


# ##################################################################
# In-memory keyring for testing
class InMemoryKeyring:
    """In-memory keyring for testing without real keyring access."""

    def __init__(self):
        self.storage = {}

    def get_password(self, service, key):
        return self.storage.get(f"{service}:{key}")

    def set_password(self, service, key, value):
        self.storage[f"{service}:{key}"] = value

    def delete_password(self, service, key):
        full_key = f"{service}:{key}"
        if full_key in self.storage:
            del self.storage[full_key]


@pytest.fixture
def inmemory_keyring(monkeypatch):
    """Fixture that provides an in-memory keyring."""
    keyring = InMemoryKeyring()
    monkeypatch.setattr("src.credentials.keyring", keyring)
    return keyring


# ##################################################################
# test save and get credential
def test_save_and_get_credential(inmemory_keyring):
    result = save_credential("test_cred", "test_type", {"user": "admin", "pass": "secret"})
    assert result is True

    cred = get_credential("test_cred", mask_private=False)
    assert cred is not None
    assert cred["type"] == "test_type"
    assert cred["data"]["user"] == "admin"
    assert cred["data"]["pass"] == "secret"


def test_get_nonexistent_credential(inmemory_keyring):
    cred = get_credential("nonexistent")
    assert cred is None


# ##################################################################
# test list credentials
def test_list_credentials_empty(inmemory_keyring):
    creds = list_credentials()
    assert creds == []


def test_list_credentials_with_items(inmemory_keyring):
    save_credential("cred1", "type1", {"key": "value1"})
    save_credential("cred2", "type2", {"key": "value2"})

    creds = list_credentials()
    assert len(creds) == 2
    names = [c["name"] for c in creds]
    assert "cred1" in names
    assert "cred2" in names


# ##################################################################
# test delete credential
def test_delete_credential(inmemory_keyring):
    save_credential("to_delete", "test_type", {"key": "value"})
    assert get_credential("to_delete") is not None

    result = delete_credential("to_delete")
    assert result is True
    assert get_credential("to_delete") is None


def test_delete_credential_removes_from_list(inmemory_keyring):
    save_credential("cred1", "type1", {"key": "value1"})
    save_credential("cred2", "type2", {"key": "value2"})

    delete_credential("cred1")

    creds = list_credentials()
    assert len(creds) == 1
    assert creds[0]["name"] == "cred2"


# ##################################################################
# test private field masking
def test_private_field_masking(inmemory_keyring, monkeypatch):
    # Stub get_credential_type to return a type with private field
    def stub_get_credential_type(type_id):
        if type_id == "test_type":
            return {
                "name": "Test",
                "properties": [
                    {"id": "user", "label": "User", "type": "text"},
                    {"id": "pass", "label": "Password", "type": "text", "private": True},
                ],
            }
        return None

    monkeypatch.setattr("src.credentials.get_credential_type", stub_get_credential_type)

    save_credential("test_cred", "test_type", {"user": "admin", "pass": "secret123"})

    # With masking (default)
    cred_masked = get_credential("test_cred", mask_private=True)
    assert cred_masked["data"]["user"] == "admin"
    assert cred_masked["data"]["pass"] == HIDE_SENTINEL

    # Without masking
    cred_unmasked = get_credential("test_cred", mask_private=False)
    assert cred_unmasked["data"]["user"] == "admin"
    assert cred_unmasked["data"]["pass"] == "secret123"


# ##################################################################
# test saving with sentinel preserves original value
def test_save_with_sentinel_preserves_value(inmemory_keyring, monkeypatch):
    def stub_get_credential_type(type_id):
        if type_id == "test_type":
            return {
                "name": "Test",
                "properties": [
                    {"id": "user", "label": "User", "type": "text"},
                    {"id": "pass", "label": "Password", "type": "text", "private": True},
                ],
            }
        return None

    monkeypatch.setattr("src.credentials.get_credential_type", stub_get_credential_type)

    # Save initial credential
    save_credential("test_cred", "test_type", {"user": "admin", "pass": "original_secret"})

    # Update with sentinel for password - should preserve original
    save_credential("test_cred", "test_type", {"user": "newuser", "pass": HIDE_SENTINEL})

    # Verify user was updated but password preserved
    cred = get_credential("test_cred", mask_private=False)
    assert cred["data"]["user"] == "newuser"
    assert cred["data"]["pass"] == "original_secret"


# ##################################################################
# test test_credential
def test_verify_credential_not_found(inmemory_keyring):
    result = verify_credential("nonexistent")
    assert result["status"] is False
    assert "not found" in result["message"]


def test_verify_credential_no_test_function(inmemory_keyring, monkeypatch):
    def stub_get_credential_type(type_id):
        if type_id == "test_type":
            return {"name": "Test", "properties": []}
        return None

    monkeypatch.setattr("src.credentials.get_credential_type", stub_get_credential_type)
    save_credential("test_cred", "test_type", {"key": "value"})

    result = verify_credential("test_cred")
    assert result["status"] is False
    assert "no test function" in result["message"]


def test_verify_credential_success(inmemory_keyring, monkeypatch):
    def stub_test_fn(data):
        return {"status": True, "message": "Connected successfully"}

    def stub_get_credential_type(type_id):
        if type_id == "test_type":
            return {"name": "Test", "properties": [], "test": stub_test_fn}
        return None

    monkeypatch.setattr("src.credentials.get_credential_type", stub_get_credential_type)
    save_credential("test_cred", "test_type", {"host": "localhost"})

    result = verify_credential("test_cred")
    assert result["status"] is True
    assert result["message"] == "Connected successfully"


def test_verify_credential_failure(inmemory_keyring, monkeypatch):
    def stub_test_fn(data):
        raise ConnectionError("Could not connect to server")

    def stub_get_credential_type(type_id):
        if type_id == "test_type":
            return {"name": "Test", "properties": [], "test": stub_test_fn}
        return None

    monkeypatch.setattr("src.credentials.get_credential_type", stub_get_credential_type)
    save_credential("test_cred", "test_type", {"host": "localhost"})

    result = verify_credential("test_cred")
    assert result["status"] is False
    assert "Could not connect" in result["message"]

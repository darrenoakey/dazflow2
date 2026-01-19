"""Tests for Discord credential definitions."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.discord_nodes.credentials import CREDENTIAL_TYPES, verify_discord


# ##################################################################
# test CREDENTIAL_TYPES registry structure
def test_credential_types_has_discord():
    assert "discord" in CREDENTIAL_TYPES


def test_discord_credential_has_name():
    assert CREDENTIAL_TYPES["discord"]["name"] == "Discord Bot"


def test_discord_credential_has_properties():
    props = CREDENTIAL_TYPES["discord"]["properties"]
    assert len(props) == 1
    assert props[0]["id"] == "bot_token"
    assert props[0]["label"] == "Bot Token"
    assert props[0]["type"] == "text"
    assert props[0]["private"] is True


def test_discord_credential_has_test_function():
    assert "test" in CREDENTIAL_TYPES["discord"]
    assert callable(CREDENTIAL_TYPES["discord"]["test"])


# ##################################################################
# test verify_discord validation
def test_verify_discord_empty_token():
    result = verify_discord({"bot_token": ""})
    assert result["status"] is False
    assert "required" in result["message"].lower()


def test_verify_discord_missing_token():
    result = verify_discord({})
    assert result["status"] is False
    assert "required" in result["message"].lower()


def test_verify_discord_whitespace_only_token():
    result = verify_discord({"bot_token": "   "})
    assert result["status"] is False
    assert "required" in result["message"].lower()


def test_verify_discord_invalid_token():
    """Test verify_discord with an invalid token format."""
    result = verify_discord({"bot_token": "invalid_token_format_abc123"})
    assert result["status"] is False
    # Should fail with login failure or invalid token
    assert "invalid" in result["message"].lower() or "timeout" in result["message"].lower()


def test_verify_discord_with_real_token():
    """Test verify_discord with real token from keyring."""
    import keyring

    token = keyring.get_password("discord_events", "token")
    assert token is not None, "Discord token not found in keyring (discord_events/token)"

    result = verify_discord({"bot_token": token})
    assert result["status"] is True
    assert "connected" in result["message"].lower()


# ##################################################################
# test CREDENTIAL_TYPES structure in detail
def test_credential_types_discord_is_dict():
    """Test that discord credential type is a dict."""
    assert isinstance(CREDENTIAL_TYPES["discord"], dict)


def test_credential_types_discord_properties_is_list():
    """Test that properties is a list."""
    assert isinstance(CREDENTIAL_TYPES["discord"]["properties"], list)


def test_credential_types_discord_first_property_complete():
    """Test that first property has all required fields."""
    prop = CREDENTIAL_TYPES["discord"]["properties"][0]
    assert "id" in prop
    assert "label" in prop
    assert "type" in prop
    assert "private" in prop


def test_credential_types_test_callable():
    """Test that test function is callable."""
    test_func = CREDENTIAL_TYPES["discord"]["test"]
    assert callable(test_func)


def test_credential_types_test_is_verify_discord():
    """Test that test function is verify_discord."""
    assert CREDENTIAL_TYPES["discord"]["test"] is verify_discord


# ##################################################################
# test cache module access
def test_discord_cache_available():
    """Test that _discord_cache is available from the module."""
    from modules.discord_nodes.credentials import _discord_cache

    assert _discord_cache is not None


def test_discord_cache_set_method():
    """Test cache has set method."""
    from modules.discord_nodes.credentials import _discord_cache

    assert hasattr(_discord_cache, "set")
    assert callable(_discord_cache.set)


def test_discord_cache_get_or_default_method():
    """Test cache has get_or_default method."""
    from modules.discord_nodes.credentials import _discord_cache

    assert hasattr(_discord_cache, "get_or_default")
    assert callable(_discord_cache.get_or_default)

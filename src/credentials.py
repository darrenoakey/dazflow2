"""
Credential storage for dazflow2.
Uses Python keyring for secure credential storage.
"""

import json

import keyring

from .module_loader import get_credential_type

KEYRING_SERVICE = "dazflow2"
HIDE_SENTINEL = "HIDE_PASSWORD_FOR_SECURITY"


def _get_credential_key(name: str) -> str:
    """Get the keyring key for a credential."""
    return f"credential:{name}"


def list_credentials() -> list[dict]:
    """List all stored credentials.

    Returns list of dicts with name and type (private fields masked).
    """
    # Keyring doesn't support listing, so we maintain an index
    index = _get_credential_index()
    result = []
    for name in index:
        cred = get_credential(name, mask_private=True)
        if cred:
            result.append({"name": name, **cred})
    return result


def _get_credential_index() -> list[str]:
    """Get the list of credential names from the index."""
    try:
        index_json = keyring.get_password(KEYRING_SERVICE, "credential_index")
        if index_json:
            return json.loads(index_json)
    except Exception:
        pass
    return []


def _save_credential_index(names: list[str]) -> None:
    """Save the credential index."""
    keyring.set_password(KEYRING_SERVICE, "credential_index", json.dumps(names))


def get_credential(name: str, mask_private: bool = True) -> dict | None:
    """Get a credential by name.

    Args:
        name: Credential name
        mask_private: If True, replace private fields with HIDE_SENTINEL

    Returns:
        Dict with type and data, or None if not found
    """
    try:
        key = _get_credential_key(name)
        stored = keyring.get_password(KEYRING_SERVICE, key)
        if not stored:
            return None

        cred = json.loads(stored)
        cred_type = cred.get("type")
        data = cred.get("data", {})

        if mask_private and cred_type:
            # Get the credential type definition to know which fields are private
            cred_type_def = get_credential_type(cred_type)
            if cred_type_def:
                for prop in cred_type_def.get("properties", []):
                    if prop.get("private") and prop["id"] in data:
                        data[prop["id"]] = HIDE_SENTINEL

        return {"type": cred_type, "data": data}
    except Exception:
        return None


def save_credential(name: str, credential_type: str, data: dict) -> bool:
    """Save or update a credential.

    Args:
        name: Credential name
        credential_type: Type of credential (e.g., "postgres")
        data: Credential data (fields matching the type's properties)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get existing credential to preserve private fields
        existing = get_credential(name, mask_private=False)

        # Merge data - keep existing values for fields that have HIDE_SENTINEL
        merged_data = {}
        for key, value in data.items():
            if value == HIDE_SENTINEL and existing:
                # Keep existing value for hidden fields
                merged_data[key] = existing.get("data", {}).get(key, "")
            else:
                merged_data[key] = value

        # Store the credential
        key = _get_credential_key(name)
        stored = json.dumps({"type": credential_type, "data": merged_data})
        keyring.set_password(KEYRING_SERVICE, key, stored)

        # Update index
        index = _get_credential_index()
        if name not in index:
            index.append(name)
            _save_credential_index(index)

        return True
    except Exception as e:
        print(f"Error saving credential: {e}")
        return False


def delete_credential(name: str) -> bool:
    """Delete a credential.

    Returns:
        True if successful, False otherwise
    """
    try:
        key = _get_credential_key(name)
        keyring.delete_password(KEYRING_SERVICE, key)

        # Update index
        index = _get_credential_index()
        if name in index:
            index.remove(name)
            _save_credential_index(index)

        return True
    except Exception:
        return False


def verify_credential(name: str) -> dict:
    """Test a credential using its type's test function.

    Returns:
        Dict with status (bool) and optional message
    """
    cred = get_credential(name, mask_private=False)
    if not cred:
        return {"status": False, "message": "Credential not found"}

    cred_type = cred.get("type")
    if not cred_type:
        return {"status": False, "message": "Credential has no type"}

    cred_type_def = get_credential_type(cred_type)
    if not cred_type_def:
        return {"status": False, "message": f"Unknown credential type: {cred_type}"}

    test_fn = cred_type_def.get("test")
    if not test_fn:
        return {"status": False, "message": f"Credential type {cred_type} has no test function"}

    try:
        result = test_fn(cred["data"])
        if isinstance(result, dict):
            return result
        return {"status": bool(result)}
    except Exception as e:
        return {"status": False, "message": str(e)}


def get_credential_for_execution(name: str) -> dict | None:
    """Get credential data for execution (unmasked).

    This is used by the executor to get real credential values.

    Returns:
        The credential data dict or None if not found
    """
    cred = get_credential(name, mask_private=False)
    if cred:
        return cred.get("data")
    return None


def test_credential_data(credential_type: str, data: dict) -> dict:
    """Test credential data without saving.

    This allows testing credentials before they are saved.

    Args:
        credential_type: Type of credential (e.g., "postgres")
        data: Credential data to test

    Returns:
        Dict with status (bool) and optional message
    """
    cred_type_def = get_credential_type(credential_type)
    if not cred_type_def:
        return {"status": False, "message": f"Unknown credential type: {credential_type}"}

    test_fn = cred_type_def.get("test")
    if not test_fn:
        return {"status": False, "message": f"Credential type {credential_type} has no test function"}

    try:
        result = test_fn(data)
        if isinstance(result, dict):
            return result
        return {"status": bool(result)}
    except Exception as e:
        return {"status": False, "message": str(e)}

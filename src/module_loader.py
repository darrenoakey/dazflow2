"""
Module loader for dazflow2.
Discovers and loads modules from the modules/ directory.
Each module can provide node types and credential types.
"""

import importlib.util
from pathlib import Path
from typing import Any

# Path to modules directory (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent
MODULES_DIR = PROJECT_ROOT / "modules"

# Cached loaded modules
_loaded_modules: dict[str, dict] = {}
_all_node_types: dict[str, dict] = {}
_all_credential_types: dict[str, dict] = {}


def _load_python_module(module_path: Path, module_name: str) -> Any | None:
    """Load a Python module from a file path."""
    if not module_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except Exception as e:
        print(f"Error loading module {module_path}: {e}")
    return None


def _load_module(module_dir: Path) -> dict:
    """Load a single module from a directory.

    Returns dict with:
        - name: Module name
        - node_types: dict of node_id -> node_type_def
        - credential_types: dict of cred_id -> cred_type_def
        - nodes_ui_path: Path to nodes_ui.js if exists
    """
    module_name = module_dir.name
    result = {
        "name": module_name,
        "node_types": {},
        "credential_types": {},
        "nodes_ui_path": None,
    }

    # Load nodes.py
    nodes_module = _load_python_module(module_dir / "nodes.py", f"{module_name}_nodes")
    if nodes_module and hasattr(nodes_module, "NODE_TYPES"):
        result["node_types"] = nodes_module.NODE_TYPES

    # Load credentials.py
    creds_module = _load_python_module(module_dir / "credentials.py", f"{module_name}_credentials")
    if creds_module and hasattr(creds_module, "CREDENTIAL_TYPES"):
        result["credential_types"] = creds_module.CREDENTIAL_TYPES

    # Check for nodes_ui.js
    nodes_ui_path = module_dir / "nodes_ui.js"
    if nodes_ui_path.exists():
        result["nodes_ui_path"] = nodes_ui_path

    return result


def discover_modules() -> list[str]:
    """Discover all modules in the modules directory."""
    if not MODULES_DIR.exists():
        return []
    return [d.name for d in MODULES_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")]


def load_all_modules(force_reload: bool = False) -> dict[str, dict]:
    """Load all modules and cache them.

    Args:
        force_reload: If True, reload all modules even if cached

    Returns:
        Dict of module_name -> module_data
    """
    global _loaded_modules, _all_node_types, _all_credential_types

    if _loaded_modules and not force_reload:
        return _loaded_modules

    _loaded_modules = {}
    _all_node_types = {}
    _all_credential_types = {}

    for module_name in discover_modules():
        module_dir = MODULES_DIR / module_name
        module_data = _load_module(module_dir)
        _loaded_modules[module_name] = module_data

        # Aggregate node types
        for node_id, node_def in module_data["node_types"].items():
            # Add module reference
            node_def_with_module = {**node_def, "module": module_name}
            _all_node_types[node_id] = node_def_with_module

        # Aggregate credential types
        for cred_id, cred_def in module_data["credential_types"].items():
            # Add module reference
            cred_def_with_module = {**cred_def, "module": module_name}
            _all_credential_types[cred_id] = cred_def_with_module

    return _loaded_modules


def get_all_node_types() -> dict[str, dict]:
    """Get all node types from all loaded modules.

    Returns dict of node_id -> node_type_def with execute function and metadata.
    """
    if not _all_node_types:
        load_all_modules()
    return _all_node_types


def get_all_credential_types() -> dict[str, dict]:
    """Get all credential types from all loaded modules.

    Returns dict of cred_id -> cred_type_def with properties and test function.
    """
    if not _all_credential_types:
        load_all_modules()
    return _all_credential_types


def get_node_type(type_id: str) -> dict | None:
    """Get a single node type definition by ID."""
    return get_all_node_types().get(type_id)


def get_credential_type(type_id: str) -> dict | None:
    """Get a single credential type definition by ID."""
    return get_all_credential_types().get(type_id)


def get_modules_ui_paths() -> list[Path]:
    """Get paths to all nodes_ui.js files."""
    if not _loaded_modules:
        load_all_modules()
    return [m["nodes_ui_path"] for m in _loaded_modules.values() if m["nodes_ui_path"]]


def get_node_types_for_api() -> list[dict]:
    """Get node types formatted for the /api/modules endpoint.

    Returns list of node type metadata (without execute functions).
    """
    node_types = get_all_node_types()
    result = []
    for node_id, node_def in node_types.items():
        # Build API-safe representation (no functions)
        api_def = {
            "id": node_id,
            "kind": node_def.get("kind", "array"),
            "module": node_def.get("module", "unknown"),
        }
        if "requiredCredential" in node_def:
            api_def["requiredCredential"] = node_def["requiredCredential"]
        result.append(api_def)
    return result


def get_credential_types_for_api() -> list[dict]:
    """Get credential types formatted for the /api/modules endpoint.

    Returns list of credential type metadata (without test functions).
    """
    cred_types = get_all_credential_types()
    result = []
    for cred_id, cred_def in cred_types.items():
        # Build API-safe representation (no functions)
        api_def = {
            "id": cred_id,
            "name": cred_def.get("name", cred_id),
            "module": cred_def.get("module", "unknown"),
            "properties": cred_def.get("properties", []),
        }
        result.append(api_def)
    return result

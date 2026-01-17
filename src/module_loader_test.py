"""Tests for module loader."""

from pathlib import Path

from src.module_loader import (
    discover_modules,
    load_all_modules,
    get_all_node_types,
    get_all_credential_types,
    get_node_type,
    get_credential_type,
    get_node_types_for_api,
    get_credential_types_for_api,
    get_modules_ui_paths,
)


# ##################################################################
# test discover_modules
# verifies modules are discovered from the modules directory
def test_discover_modules_finds_core_and_postgres():
    modules = discover_modules()
    assert "core" in modules
    assert "postgres" in modules


def test_discover_modules_ignores_underscore_dirs(tmp_path, monkeypatch):
    # Create a modules directory with _ prefixed dir
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()
    (modules_dir / "valid").mkdir()
    (modules_dir / "_hidden").mkdir()

    monkeypatch.setattr("src.module_loader.MODULES_DIR", modules_dir)

    # Force reload to use new path
    import src.module_loader as ml

    ml._loaded_modules = {}
    ml._all_node_types = {}
    ml._all_credential_types = {}

    modules = discover_modules()
    assert "valid" in modules
    assert "_hidden" not in modules


# ##################################################################
# test load_all_modules
# verifies modules are loaded and cached
def test_load_all_modules_returns_dict():
    modules = load_all_modules(force_reload=True)
    assert isinstance(modules, dict)
    assert "core" in modules
    assert "postgres" in modules


def test_load_all_modules_caches_result():
    # First load
    modules1 = load_all_modules(force_reload=True)
    # Second load (should be cached)
    modules2 = load_all_modules()
    assert modules1 is modules2


def test_load_all_modules_force_reload():
    # First load
    modules1 = load_all_modules(force_reload=True)
    # Force reload creates new dicts
    modules2 = load_all_modules(force_reload=True)
    # Verify both have same module names (content differs due to new function refs)
    assert set(modules1.keys()) == set(modules2.keys())
    # Verify structures are similar
    for module_name in modules1:
        assert modules1[module_name]["name"] == modules2[module_name]["name"]
        assert set(modules1[module_name]["node_types"].keys()) == set(modules2[module_name]["node_types"].keys())


# ##################################################################
# test get_all_node_types
# verifies node types are aggregated from all modules
def test_get_all_node_types_includes_core_types():
    load_all_modules(force_reload=True)
    node_types = get_all_node_types()
    # Core module should provide these types
    assert "start" in node_types
    assert "scheduled" in node_types
    assert "set" in node_types
    assert "if" in node_types


def test_get_all_node_types_includes_postgres():
    load_all_modules(force_reload=True)
    node_types = get_all_node_types()
    assert "postgres_query" in node_types


def test_get_all_node_types_have_module_reference():
    load_all_modules(force_reload=True)
    node_types = get_all_node_types()
    assert node_types["start"]["module"] == "core"
    assert node_types["postgres_query"]["module"] == "postgres"


# ##################################################################
# test get_all_credential_types
# verifies credential types are aggregated from all modules
def test_get_all_credential_types_includes_postgres():
    load_all_modules(force_reload=True)
    cred_types = get_all_credential_types()
    assert "postgres" in cred_types


def test_get_all_credential_types_have_module_reference():
    load_all_modules(force_reload=True)
    cred_types = get_all_credential_types()
    assert cred_types["postgres"]["module"] == "postgres"


# ##################################################################
# test get_node_type
# verifies single node type lookup
def test_get_node_type_returns_type():
    load_all_modules(force_reload=True)
    node_type = get_node_type("start")
    assert node_type is not None
    assert "execute" in node_type
    assert node_type["kind"] == "array"


def test_get_node_type_returns_none_for_unknown():
    load_all_modules(force_reload=True)
    node_type = get_node_type("nonexistent_type")
    assert node_type is None


# ##################################################################
# test get_credential_type
# verifies single credential type lookup
def test_get_credential_type_returns_type():
    load_all_modules(force_reload=True)
    cred_type = get_credential_type("postgres")
    assert cred_type is not None
    assert cred_type["name"] == "PostgreSQL"


def test_get_credential_type_returns_none_for_unknown():
    load_all_modules(force_reload=True)
    cred_type = get_credential_type("nonexistent_type")
    assert cred_type is None


# ##################################################################
# test get_node_types_for_api
# verifies API-safe node type representation
def test_get_node_types_for_api_returns_list():
    load_all_modules(force_reload=True)
    api_types = get_node_types_for_api()
    assert isinstance(api_types, list)
    assert len(api_types) > 0


def test_get_node_types_for_api_has_required_fields():
    load_all_modules(force_reload=True)
    api_types = get_node_types_for_api()
    for api_type in api_types:
        assert "id" in api_type
        assert "kind" in api_type
        assert "module" in api_type


def test_get_node_types_for_api_includes_required_credential():
    load_all_modules(force_reload=True)
    api_types = get_node_types_for_api()
    postgres_type = next((t for t in api_types if t["id"] == "postgres_query"), None)
    assert postgres_type is not None
    assert postgres_type["requiredCredential"] == "postgres"


def test_get_node_types_for_api_excludes_execute_function():
    load_all_modules(force_reload=True)
    api_types = get_node_types_for_api()
    for api_type in api_types:
        assert "execute" not in api_type


# ##################################################################
# test get_credential_types_for_api
# verifies API-safe credential type representation
def test_get_credential_types_for_api_returns_list():
    load_all_modules(force_reload=True)
    api_types = get_credential_types_for_api()
    assert isinstance(api_types, list)


def test_get_credential_types_for_api_has_required_fields():
    load_all_modules(force_reload=True)
    api_types = get_credential_types_for_api()
    for api_type in api_types:
        assert "id" in api_type
        assert "name" in api_type
        assert "module" in api_type
        assert "properties" in api_type


def test_get_credential_types_for_api_excludes_test_function():
    load_all_modules(force_reload=True)
    api_types = get_credential_types_for_api()
    for api_type in api_types:
        assert "test" not in api_type


# ##################################################################
# test get_modules_ui_paths
# verifies UI paths are collected
def test_get_modules_ui_paths_returns_paths():
    load_all_modules(force_reload=True)
    paths = get_modules_ui_paths()
    assert isinstance(paths, list)
    # Should have at least core and postgres ui paths
    assert len(paths) >= 2


def test_get_modules_ui_paths_are_valid():
    load_all_modules(force_reload=True)
    paths = get_modules_ui_paths()
    for path in paths:
        assert isinstance(path, Path)
        assert path.exists()
        assert path.name == "nodes_ui.js"

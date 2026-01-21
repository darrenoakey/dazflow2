"""Tests for server configuration."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import ServerConfig, get_config, set_config


# ##################################################################
# test default values
def test_default_config_values():
    config = ServerConfig()
    assert config.port == 5000
    assert config.data_dir == "."


# ##################################################################
# test custom values
def test_custom_config_values():
    config = ServerConfig(port=8080, data_dir="/custom/path")
    assert config.port == 8080
    assert config.data_dir == "/custom/path"


# ##################################################################
# test property paths
def test_workflows_dir_property():
    config = ServerConfig(data_dir="/test/data")
    assert config.workflows_dir == "/test/data/workflows"


def test_workflows_dir_property_with_dot():
    config = ServerConfig(data_dir=".")
    assert config.workflows_dir == "workflows"


def test_agents_file_property():
    config = ServerConfig(data_dir="/test/data")
    assert config.agents_file == "/test/data/agents.json"


def test_agents_file_property_with_dot():
    config = ServerConfig(data_dir=".")
    assert config.agents_file == "agents.json"


def test_tags_file_property():
    config = ServerConfig(data_dir="/test/data")
    assert config.tags_file == "/test/data/tags.json"


def test_tags_file_property_with_dot():
    config = ServerConfig(data_dir=".")
    assert config.tags_file == "tags.json"


def test_concurrency_groups_file_property():
    config = ServerConfig(data_dir="/test/data")
    assert config.concurrency_groups_file == "/test/data/concurrency_groups.json"


def test_concurrency_groups_file_property_with_dot():
    config = ServerConfig(data_dir=".")
    assert config.concurrency_groups_file == "concurrency_groups.json"


# ##################################################################
# test get_config and set_config
def test_get_config_creates_default():
    # Reset global config
    import config as config_module

    config_module._config = None

    cfg = get_config()
    assert cfg.port == 5000
    assert cfg.data_dir == "."


def test_get_config_returns_same_instance():
    # Reset global config
    import config as config_module

    config_module._config = None

    config1 = get_config()
    config2 = get_config()
    assert config1 is config2


def test_set_config_changes_global():
    # Reset global config
    import config as config_module

    config_module._config = None

    custom_config = ServerConfig(port=9000, data_dir="/custom")
    set_config(custom_config)

    retrieved = get_config()
    assert retrieved is custom_config
    assert retrieved.port == 9000
    assert retrieved.data_dir == "/custom"


def test_set_config_overrides_previous():
    # Reset global config
    import config as config_module

    config_module._config = None

    config1 = ServerConfig(port=8000, data_dir="/first")
    set_config(config1)

    config2 = ServerConfig(port=9000, data_dir="/second")
    set_config(config2)

    retrieved = get_config()
    assert retrieved is config2
    assert retrieved.port == 9000
    assert retrieved.data_dir == "/second"


# ##################################################################
# test path handling
def test_workflows_dir_with_relative_path():
    config = ServerConfig(data_dir="local/work")
    assert config.workflows_dir == "local/work/workflows"


def test_workflows_dir_with_absolute_path():
    config = ServerConfig(data_dir="/absolute/path")
    assert config.workflows_dir == "/absolute/path/workflows"


def test_multiple_properties_use_same_data_dir():
    config = ServerConfig(data_dir="/shared")
    assert config.workflows_dir == "/shared/workflows"
    assert config.agents_file == "/shared/agents.json"
    assert config.tags_file == "/shared/tags.json"
    assert config.concurrency_groups_file == "/shared/concurrency_groups.json"


# ##################################################################
# test edge cases
def test_empty_data_dir():
    config = ServerConfig(data_dir="")
    assert config.workflows_dir == "workflows"
    assert config.agents_file == "agents.json"


def test_port_zero():
    config = ServerConfig(port=0)
    assert config.port == 0


def test_high_port_number():
    config = ServerConfig(port=65535)
    assert config.port == 65535


# ##################################################################
# test agent version property
# verifies agent_version returns code hash
def test_agent_version_property():
    config = ServerConfig()
    version = config.agent_version
    assert isinstance(version, str)
    # Should be a 12-character hash
    assert len(version) == 12


# ##################################################################
# test agent version is deterministic
# verifies agent_version returns same value on repeated calls
def test_agent_version_is_deterministic():
    config = ServerConfig()
    v1 = config.agent_version
    v2 = config.agent_version
    assert v1 == v2

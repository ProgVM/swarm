import os
import json
import pytest
from swarm.exceptions import SwarmConfigError
from swarm.config import ConfigManager

def test_missing_config_file():
    # Verification that invalid/non-existent directory in path raises SwarmConfigError
    with pytest.raises(SwarmConfigError) as exc_info:
        ConfigManager.validate({"save_file": "non_existent_directory_abc123/session.json"})
    assert "Directory for save_file does not exist" in str(exc_info.value)

def test_config_is_directory():
    # Verification that save_file being a directory path raises SwarmConfigError
    with pytest.raises(SwarmConfigError) as exc_info:
        ConfigManager.validate({"save_file": "."})
    assert "save_file path is a directory" in str(exc_info.value)

def test_agents_count_validation():
    with pytest.raises(SwarmConfigError, match="agents_count must be positive"):
        ConfigManager.validate({"agents_count": 0})
    with pytest.raises(SwarmConfigError, match="agents_count must be positive"):
        ConfigManager.validate({"agents_count": -5})
    with pytest.raises(SwarmConfigError, match="agents_count must be an integer"):
        ConfigManager.validate({"agents_count": "invalid_string"})

def test_max_history_validation():
    with pytest.raises(SwarmConfigError, match="max_history must be positive"):
        ConfigManager.validate({"max_history": 0})
    with pytest.raises(SwarmConfigError, match="max_history must be positive"):
        ConfigManager.validate({"max_history": -1})
    with pytest.raises(SwarmConfigError, match="max_history must be an integer"):
        ConfigManager.validate({"max_history": "invalid_string"})

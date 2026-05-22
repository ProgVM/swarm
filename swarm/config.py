import os
import collections.abc
from swarm.schema import CONFIG_SCHEMA
from swarm.exceptions import SwarmConfigError

class ConfigManager:
    @staticmethod
    def deep_merge(source, destination, _visited=None):
        if _visited is None:
            _visited = set()
            
        source_id = id(source)
        if source_id in _visited:
            raise ValueError("Cyclic reference detected in configuration.")
        _visited.add(source_id)

        for key, value in source.items():
            if isinstance(value, collections.abc.Mapping):
                node = destination.setdefault(key, {})
                ConfigManager.deep_merge(value, node, _visited)
            else:
                destination[key] = value
        return destination

    @staticmethod
    def cast_value(key, value):
        if key not in CONFIG_SCHEMA:
            return value
        
        target_type = CONFIG_SCHEMA[key]
        try:
            return target_type(value)
        except (ValueError, TypeError):
            raise SwarmConfigError(f"Field '{key}' expects {target_type.__name__}, got '{value}' ({type(value).__name__})")

    @staticmethod
    def merge(defaults, session_data, cli_args):
        # 1. Start with defaults
        config = defaults.copy()
        
        # 2. Deep merge session data
        ConfigManager.deep_merge(session_data, config)
        
        # 3. Deep merge CLI args
        ConfigManager.deep_merge(cli_args, config)
        
        # 4. Final casting/validation
        for k, v in config.items():
            config[k] = ConfigManager.cast_value(k, v)
            
        return config

    @staticmethod
    def validate(config):
        """Validates configuration parameters, checking file path access and correctness of settings."""
        # Validate that if save_file is provided, its directory exists and is writable
        save_file = config.get("save_file")
        if save_file:
            try:
                abs_path = os.path.abspath(save_file)
                dir_name = os.path.dirname(abs_path)
            except Exception as e:
                raise SwarmConfigError(f"Invalid path format for save_file: {save_file}. Error: {e}")

            if os.path.isdir(abs_path):
                raise SwarmConfigError(f"save_file path is a directory, expected a file path: {save_file}")
                
            if not os.path.exists(dir_name):
                raise SwarmConfigError(f"Directory for save_file does not exist: {dir_name}")
                
            if not os.access(dir_name, os.W_OK):
                raise SwarmConfigError(f"Directory for save_file is not writable: {dir_name}")

        # Validate positive numeric attributes
        agents_count = config.get("agents_count")
        if agents_count is not None:
            try:
                agents_count_val = int(agents_count)
                if agents_count_val <= 0:
                    raise SwarmConfigError(f"agents_count must be positive, got {agents_count_val}")
            except (ValueError, TypeError):
                raise SwarmConfigError(f"agents_count must be an integer, got '{agents_count}'")

        max_history = config.get("max_history")
        if max_history is not None:
            try:
                max_history_val = int(max_history)
                if max_history_val <= 0:
                    raise SwarmConfigError(f"max_history must be positive, got {max_history_val}")
            except (ValueError, TypeError):
                raise SwarmConfigError(f"max_history must be an integer, got '{max_history}'")

        return True

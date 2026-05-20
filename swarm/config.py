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

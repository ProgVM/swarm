import logging
from .result import ToolResult

logger = logging.getLogger("Swarm.Tools")

class ToolAlreadyRegisteredError(Exception): pass

class ToolRegistry:
    _tools = {}
    _schemas = {}

    @classmethod
    def register(cls, name, func, schema, overwrite=False):
        if name in cls._tools and not overwrite:
            raise ToolAlreadyRegisteredError(f"Tool '{name}' is already registered.")
        cls._tools[name] = func
        cls._schemas[name] = schema
        logger.info(f"Tool '{name}' registered.")

    @classmethod
    def get_all_definitions(cls):
        return cls._schemas

    @classmethod
    def execute(cls, name, args, agent, client):
        if name not in cls._tools:
            return ToolResult(success=False, error=f"Tool '{name}' not found.")
        try:
            result = cls._tools[name](args, agent, client)
            return result if isinstance(result, ToolResult) else ToolResult(success=True, data=result)
        except Exception as e:
            logger.error(f"Tool '{name}' failed: {e}")
            return ToolResult(success=False, error=str(e))

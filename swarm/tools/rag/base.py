from abc import ABC, abstractmethod
from ..result import ToolResult

class BaseRetriever(ABC):
    @abstractmethod
    def index(self, path: str) -> ToolResult:
        """Indexes the content of a file or directory."""
        pass

    @abstractmethod
    def query(self, text: str, top_k: int = 3) -> ToolResult:
        """Queries the index for relevant information."""
        pass

    @abstractmethod
    def clear(self) -> ToolResult:
        """Clears the index."""
        pass

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class RetrievalResult:
    content: str
    metadata: Dict

class BaseRetriever(ABC):
    @abstractmethod
    def index(self, path: str) -> bool:
        """Indexes file/directory content."""
        pass

    @abstractmethod
    def query(self, text: str, top_k: int = 3) -> List[RetrievalResult]:
        """Queries the index for relevant fragments."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears the index."""
        pass

class ContextManager:
    MAX_CONTEXT_TOKENS = 15000 

    @staticmethod
    def prepare_context(results: List[RetrievalResult]) -> str:
        context_parts = []
        total_len = 0
        
        for res in results:
            snippet = f"--- Source: {res.metadata.get('source', 'unknown')} ---\n{res.content}\n"
            if (total_len + len(snippet)) / 4 < ContextManager.MAX_CONTEXT_TOKENS:
                context_parts.append(snippet)
                total_len += len(snippet)
            else:
                break
        
        return "\n".join(context_parts) if context_parts else "No relevant context found."

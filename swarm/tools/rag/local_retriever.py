import os
import json
from typing import List
from ...retriever import BaseRetriever, RetrievalResult
from ..result import ToolResult

class LocalFileRetriever(BaseRetriever):
    def __init__(self, index_path="rag_index.json"):
        self.index_path = index_path
        self.index_data = {}
        self._load_index()

    def _load_index(self):
        if os.path.exists(self.index_path):
            with open(self.index_path, 'r') as f:
                self.index_data = json.load(f)

    def _save_index(self):
        with open(self.index_path, 'w') as f:
            json.dump(self.index_data, f)

    def index(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        
        # Simple implementation: read file content as one chunk
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        self.index_data[path] = content
        self._save_index()
        return True

    def query(self, text: str, top_k: int = 3) -> List[RetrievalResult]:
        results = []
        for path, content in self.index_data.items():
            if text.lower() in content.lower():
                results.append(RetrievalResult(content=content, metadata={"source": path}))
        return results[:top_k]

    def clear(self) -> None:
        self.index_data = {}
        if os.path.exists(self.index_path):
            os.remove(self.index_path)

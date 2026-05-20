from .local_retriever import LocalFileRetriever
from ...retriever import ContextManager
from ..result import ToolResult

class RAGTool:
    def __init__(self, retriever: LocalFileRetriever):
        self.retriever = retriever

    def get_schema(self):
        return {
            "name": "rag_query",
            "description": "Query the RAG index for relevant information.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"query": {"type": "STRING"}},
                "required": ["query"]
            }
        }

    def run(self, args, agent, client):
        query = args.get("query")
        results = self.retriever.query(query)
        context = ContextManager.prepare_context(results)
        return ToolResult(success=True, data=context)

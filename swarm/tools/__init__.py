from .registry import ToolRegistry
from .result import ToolResult
from .shell import shell_exec
from .web import web_search
from .upload import upload_file
from .rag.rag_tool import RAGTool
from .rag.local_retriever import LocalFileRetriever

# Register standard tools
ToolRegistry.register("shell_exec", shell_exec, {
    "name": "shell_exec",
    "description": "Run bash commands.",
    "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}
})

ToolRegistry.register("web_search", web_search, {
    "name": "web_search",
    "description": "Search the web.",
    "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}
})

ToolRegistry.register("upload_file", upload_file, {
    "name": "upload_file",
    "description": "Upload local file.",
    "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]}
})

def pass_turn(args, agent, client):
    return "Use pass_turn tool"

ToolRegistry.register("pass_turn", pass_turn, {
    "name": "pass_turn",
    "description": "Delegate to peer.",
    "parameters": {"type": "OBJECT", "properties": {"agent_name": {"type": "STRING"}}, "required": ["agent_name"]}
})

# Register RAG tool
retriever = LocalFileRetriever()
rag_tool = RAGTool(retriever)
ToolRegistry.register("rag_query", rag_tool.run, rag_tool.get_schema())

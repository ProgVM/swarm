import json
from ddgs import DDGS
from swarm.tools.result import ToolResult

def web_search(args, agent, client):
    query = args.get("query")
    max_results = agent.max_search
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
        return ToolResult(success=True, data=json.dumps(results, ensure_ascii=False, indent=2) if results else "No results.")
    except Exception as e:
        return ToolResult(success=False, error=str(e))

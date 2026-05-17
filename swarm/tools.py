import subprocess
import json
import re
import time
import os
import logging
from ddgs import DDGS

logger = logging.getLogger("Swarm.Tools")

class ToolRegistry:
    """Registry of core tools with security filtering."""
    
    @staticmethod
    def web_search(query, max_results=5):
        logger.debug(f"Tool call: Web Search -> {query}")
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=max_results)]
            return json.dumps(results, ensure_ascii=False, indent=2) if results else "No results."
        except Exception as e:
            return f"Search Error: {str(e)}"

    @staticmethod
    def shell_exec(command, timeout=300, blacklist=None):
        logger.debug(f"Tool call: Shell Exec -> {command}")
        if blacklist:
            for pattern in blacklist:
                if re.search(pattern, command, re.IGNORECASE):
                    return f"Error: Command blocked by security policy (matches {pattern})."
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            out = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            return out if out.strip() else "Success (no output)."
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout}s."
        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    def upload_file(client, path, blacklist=None):
        if not os.path.exists(path):
            return {"error": "File not found."}
        if blacklist:
            for pattern in blacklist:
                if re.search(pattern, path, re.IGNORECASE):
                    return {"error": "File access blocked."}
        try:
            file_obj = client.files.upload(path=path)
            while file_obj.state.name == "PROCESSING":
                time.sleep(2)
                file_obj = client.files.get(name=file_obj.name)
            return {"uri": file_obj.uri, "mime": file_obj.mime_type, "name": file_obj.name}
        except Exception as e:
            return {"error": str(e)}

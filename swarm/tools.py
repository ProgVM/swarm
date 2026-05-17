import subprocess
import json
import re
import time
import logging
from ddgs import DDGS

logger = logging.getLogger("Swarm.Tools")

class ToolRegistry:
    """Static container for all tool logic with built-in security and limits."""

    @staticmethod
    def web_search(query, max_results=5):
        """Standard web search tool."""
        logger.debug(f"Searching for: {query} (limit: {max_results})")
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=max_results)]
            if not results:
                return "No search results found."
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"DDGS Error: {e}")
            return f"Search failed: {str(e)}"

    @staticmethod
    def shell_exec(command, timeout=300, blacklist=None):
        """Secure shell execution tool."""
        logger.debug(f"Executing: {command} (timeout: {timeout})")
        if blacklist:
            for pattern in blacklist:
                if re.search(pattern, command, re.IGNORECASE):
                    logger.warning(f"Blocked command: {command} (matches {pattern})")
                    return f"Security Exception: Command matches blacklist pattern '{pattern}'."
        
        try:
            res = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            output = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
            return output if output.strip() else "Executed successfully with no output."
        except subprocess.TimeoutExpired:
            return f"Timeout Error: Command exceeded {timeout} seconds."
        except Exception as e:
            return f"Execution failed: {str(e)}"

    @staticmethod
    def upload_file(client, path, blacklist=None):
        """Google Files API wrapper."""
        if not os.path.exists(path):
            return {"error": f"Path '{path}' does not exist."}
        
        if blacklist:
            for pattern in blacklist:
                if re.search(pattern, path, re.IGNORECASE):
                    return {"error": f"Access to '{path}' is denied by security policy."}

        logger.info(f"Uploading file: {path}")
        try:
            file_obj = client.files.upload(path=path)
            while file_obj.state.name == "PROCESSING":
                time.sleep(2)
                file_obj = client.files.get(name=file_obj.name)
            
            if file_obj.state.name == "FAILED":
                return {"error": "Server-side file processing failed."}
                
            return {
                "uri": file_obj.uri, 
                "mime": file_obj.mime_type, 
                "name": file_obj.name
            }
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return {"error": str(e)}

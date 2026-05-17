import subprocess
import json
import re
import time
import os
import logging
from ddgs import DDGS

logger = logging.getLogger("Swarm.Tools")

class ToolRegistry:
    """Core capabilities provided to autonomous agents."""
    
    @staticmethod
    def web_search(query, max_results=5):
        """Standard web search via DuckDuckGo."""
        logger.debug(f"Search Query: {query}")
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=max_results)]
            if not results:
                return "System: No relevant web results found."
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"System Error: Web search unavailable ({e})"

    @staticmethod
    def shell_exec(command, timeout=300, blacklist=None):
        """
        Executes bash commands with regex-based security filtering.
        Default timeout is 300s to avoid hanging.
        """
        logger.debug(f"Terminal Command: {command}")
        if blacklist:
            for pattern in blacklist:
                if re.search(pattern, command, re.IGNORECASE):
                    logger.warning(f"BLOCKED: {command} matches {pattern}")
                    return f"Security Exception: Command execution denied by policy."
        
        try:
            res = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            
            output = []
            if stdout: output.append(f"STDOUT:\n{stdout}")
            if stderr: output.append(f"STDERR:\n{stderr}")
            
            return "\n".join(output) if output else "System: Execution successful (no output)."
        except subprocess.TimeoutExpired:
            return f"System Error: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"System Error: Critical failure ({str(e)})"

    @staticmethod
    def upload_file(client, path, blacklist=None):
        """Uploads local files to the Google Cloud for multimodal analysis."""
        if not os.path.exists(path):
            return {"error": f"File '{path}' not found."}
            
        if blacklist:
            for pattern in blacklist:
                if re.search(pattern, path, re.IGNORECASE):
                    return {"error": "Access to this file path is restricted."}

        logger.info(f"Uploading asset: {path}")
        try:
            file_obj = client.files.upload(path=path)
            # Wait for Google server-side processing
            while file_obj.state.name == "PROCESSING":
                time.sleep(2)
                file_obj = client.files.get(name=file_obj.name)
            
            if file_obj.state.name == "FAILED":
                return {"error": "Google API failed to process the file."}
                
            return {
                "uri": file_obj.uri, 
                "mime": file_obj.mime_type, 
                "name": file_obj.name
            }
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return {"error": str(e)}

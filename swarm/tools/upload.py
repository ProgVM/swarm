import os
import re
import time
import logging
from google.genai import types
from .result import ToolResult

logger = logging.getLogger("Swarm.Tools.Upload")

def upload_file(args, agent, client):
    path = args.get("path")
    blacklist = agent.file_blacklist
    
    if not os.path.exists(path):
        return ToolResult(success=False, error=f"File '{path}' not found.")
        
    if blacklist:
        for pattern in blacklist:
            if re.search(pattern, path, re.IGNORECASE):
                return ToolResult(success=False, error="Access to this file path is restricted.")

    logger.info(f"Uploading asset: {path}")
    try:
        file_obj = client.files.upload(path=path)
        # Wait for Google server-side processing
        while file_obj.state.name == "PROCESSING":
            time.sleep(2)
            file_obj = client.files.get(name=file_obj.name)
        
        if file_obj.state.name == "FAILED":
            return ToolResult(success=False, error="Google API failed to process the file.")
            
        # Inject FileData so the model can actually "see" the file content
        agent.history.append(types.Content(
            role="user", 
            parts=[types.Part(file_data=types.FileData(file_uri=file_obj.uri, mime_type=file_obj.mime_type))]
        ))
        
        return ToolResult(success=True, data=f"System: File uploaded to {file_obj.uri}")
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return ToolResult(success=False, error=str(e))

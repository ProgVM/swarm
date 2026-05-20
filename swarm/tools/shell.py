import subprocess
import re
from swarm.tools.result import ToolResult

def shell_exec(args, agent, client):
    command = args.get("command")
    timeout = agent.cmd_timeout
    blacklist = agent.cmd_blacklist
    
    if blacklist:
        for pattern in blacklist:
            if re.search(pattern, command, re.IGNORECASE):
                return ToolResult(success=False, error="Command execution denied by policy.")
    
    try:
        res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return ToolResult(success=True, data=f"STDOUT:\n{res.stdout.strip()}\nSTDERR:\n{res.stderr.strip()}")
    except Exception as e:
        return ToolResult(success=False, error=str(e))

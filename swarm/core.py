import logging
import json
import time
from google import genai
from google.genai import types

from .utils import Colors, Serializer, create_backup
from .tools import ToolRegistry, ToolResult
from .exceptions import SwarmDataError
from .validator import SessionValidator
from .memory import MemoryManager
from .logger import EventLogger

logger = logging.getLogger("Swarm.Core")

class Agent:
    def __init__(self, agent_id, name, description, config):
        self.id = agent_id
        self.name = name
        self.description = description
        self.model = config.get('model', 'gemini-3.5-flash')
        self.sys_prompt = config.get('sys_prompt', 'You are a helpful agent.')
        self.temperature = float(config.get('temp', 0.7))
        self.history = []
        self.tools_enabled = config.get('tools', ["web_search", "shell_exec", "upload_file", "pass_turn"])
        self.max_search = int(config.get('max_search', 5))
        self.cmd_timeout = int(config.get('cmd_timeout', 300))
        self.cmd_blacklist = config.get('cmd_blacklist', [])
        self.file_blacklist = config.get('file_blacklist', [])

class SwarmSession:
    def __init__(self, args, keys):
        self.args = args
        self.keys = keys
        self.key_idx = 0
        self.client = genai.Client(api_key=self.keys[self.key_idx])
        self.agents = []
        self.current_agent_idx = 0
        self.last_interaction = getattr(args, 'first_msg', "Hello.")
        self.enable_pauses = not getattr(args, 'no_pause', False)
        self.turn_passed_manually = False
        self.memory = MemoryManager(max_history=10)
        self._init_agents(args)

    def _init_agents(self, args):
        arg_dict = vars(args)
        for i in range(getattr(args, 'agents_count', 1)):
            p = f"ai{i+1}_"
            config = {
                'model': arg_dict.get(f"{p}model", getattr(args, 'model', 'gemini-3.1-flash-lite')),
                'sys_prompt': arg_dict.get(f"{p}sys", getattr(args, f'sys{i+1}', 'You are a helpful agent.')),
                'temp': arg_dict.get(f"{p}temp", getattr(args, 'temp', 0.7)),
                'tools': arg_dict.get(f"{p}tools", ["web_search", "shell_exec", "upload_file", "pass_turn"]),
                'max_search': arg_dict.get(f"{p}max_search", getattr(args, 'max_results', 5)),
                'cmd_timeout': arg_dict.get(f"{p}cmd_timeout", getattr(args, 'cmd_timeout', 300)),
                'cmd_blacklist': arg_dict.get(f"{p}cmd_blacklist", getattr(args, 'cmd_blacklist', [])),
                'file_blacklist': arg_dict.get(f"{p}file_blacklist", getattr(args, 'file_blacklist', [])),
            }
            name = arg_dict.get(f"{p}name", f"Agent_{i+1}")
            desc = arg_dict.get(f"{p}desc", "An autonomous participant in the Swarm.")
            self.agents.append(Agent(i+1, name, desc, config))

    def load_and_validate(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            SessionValidator.validate(data)
            if data.get("version") != "1.0": raise SwarmDataError(f"Unsupported version: {data.get('version')}")
            if data["current_agent"] >= len(data["histories"]): raise SwarmDataError("Invalid index.")
            self.current_agent_idx = data["current_agent"]
            self.last_interaction = data["last_interaction"]
            return data
        except Exception as e: raise SwarmDataError(f"Failed to load: {str(e)}")

    def validate_indices(self):
        if self.current_agent_idx >= len(self.agents) or self.current_agent_idx < 0:
            self.current_agent_idx = 0

    def rotate_key(self):
        if len(self.keys) > 1:
            self.key_idx = (self.key_idx + 1) % len(self.keys)
            self.client = genai.Client(api_key=self.keys[self.key_idx])
            return True
        return False

    def _build_root_prompt(self, agent):
        swarm_map = "\n".join([f"- {a.name} (ID: {a.id}): {a.description}" for a in self.agents])
        return f"{agent.sys_prompt}\n\n--- SWARM ARCHITECTURE ---\nYOUR NAME: {agent.name}\nPARTICIPANTS:\n{swarm_map}\n\nRULES:\n1. Use tools.\n2. Use 'pass_turn' to delegate."

    def execute_step(self):
        self.validate_indices()
        agent = self.agents[self.current_agent_idx]
        
        # Initialize reports and reset manual turn flag
        reports = []
        self.turn_passed_manually = False
        full_output_text = ""
        
        agent.history, _ = self.memory.manage_history(agent.history)
        agent.history.append(types.Content(role="user", parts=[types.Part(text=self.last_interaction)]))
        
        session_file = getattr(self.args, 'save_file', 'swarm_session.json')
        
        while True:
            try:
                active_tools = [{"function_declarations": [ToolRegistry.get_all_definitions()[t]]} 
                                for t in agent.tools_enabled if t in ToolRegistry.get_all_definitions()]
                
                config = types.GenerateContentConfig(system_instruction=self._build_root_prompt(agent), tools=active_tools if active_tools else None)
                resp = self.client.models.generate_content(model=agent.model, config=config, contents=agent.history)
                
                candidate = resp.candidates[0]
                current_chunk = "".join([p.text for p in candidate.content.parts if p.text])
                if current_chunk:
                    if full_output_text:
                        full_output_text += "\n" + current_chunk
                    else:
                        full_output_text = current_chunk

                calls = [p.function_call for p in candidate.content.parts if p.function_call]
                
                if not calls:
                    agent.history.append(candidate.content)
                    self.last_interaction = full_output_text
                    return full_output_text.strip(), reports

                agent.history.append(candidate.content)
                tool_results = []
                
                for call in calls:
                    EventLogger.log_event(session_file, "TOOL_INVOKED", agent.name, data={"tool": call.name})
                    
                    if call.name == "pass_turn":
                        target = call.args.get("agent_name")
                        for i, a in enumerate(self.agents):
                            if a.name == target: self.current_agent_idx = i; self.turn_passed_manually = True; break
                        res = ToolResult(success=True, data="Turn passed.")
                    else:
                        res = ToolRegistry.execute(call.name, call.args, agent, self.client)
                    
                    EventLogger.log_event(session_file, "TOOL_RESULT", agent.name, data={"tool": call.name, "success": res.success})
                    tool_results.append(types.Part.from_function_response(name=call.name, response={"result": str(res)}))
                    reports.append(f"Shared Report: {agent.name} used {call.name}. Output: {str(res)[:150]}...")

                agent.history.append(types.Content(role="tool", parts=tool_results))

            except Exception as e:
                err_str = str(e)
                if "429" in err_str:
                    logger.warning("Quota limit hit (429). Rotating API keys.")
                    if self.rotate_key():
                        continue
                    else:
                        return f"Internal Framework Error: All API keys exhausted. ({e})", []
                elif "503" in err_str or "500" in err_str:
                    logger.warning(f"Temporary API error ({err_str}). Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                
                logger.error(f"Agent Cycle Error: {e}")
                return f"Internal Framework Error: {e}", []

import logging
import json
import time
from google import genai
from google.genai import types

from .utils import Colors, Serializer, create_backup, get_turn_role, get_turn_parts
from .tools import ToolRegistry, ToolResult
from .exceptions import SwarmDataError
from .validator import SessionValidator
from .memory import MemoryManager
from .logger import EventLogger

logger = logging.getLogger("Swarm.Core")

def clean_history(history):
    """
    Cleans up the history list to ensure it strictly conforms to Gemini's alternation rules.
    Specifically:
    1. Removes any empty content turns.
    2. Merges consecutive turns of the same role (user-user or model-model) into a single turn
       by extending the list of parts.
    """
    if not history:
        return []
        
    cleaned = []
    for turn in history:
        role = get_turn_role(turn)
        parts = get_turn_parts(turn)
        
        if not role:
            continue
            
        if cleaned and get_turn_role(cleaned[-1]) == role:
            # Merge parts
            last_turn = cleaned[-1]
            if hasattr(last_turn, "parts"):
                if last_turn.parts is None:
                    last_turn.parts = []
                last_turn.parts.extend(parts)
            elif isinstance(last_turn, dict):
                if "parts" not in last_turn or last_turn["parts"] is None:
                    last_turn["parts"] = []
                last_turn["parts"].extend(parts)
        else:
            # Create a shallow copy to preserve types
            if hasattr(turn, "role"):
                cleaned.append(types.Content(role=role, parts=list(parts)))
            else:
                cleaned.append({"role": role, "parts": list(parts)})
                
    return cleaned

def safe_append_to_history(history, role, parts):
    """
    Appends parts to the history list under the given role.
    If the last turn in history already has the same role, it extends its parts.
    Otherwise, it appends a new Content object.
    """
    p_list = []
    for p in parts:
        if isinstance(p, str):
            p_list.append(types.Part(text=p))
        else:
            p_list.append(p)
            
    if history and get_turn_role(history[-1]) == role:
        last_turn = history[-1]
        if hasattr(last_turn, "parts"):
            if last_turn.parts is None:
                last_turn.parts = []
            last_turn.parts.extend(p_list)
        elif isinstance(last_turn, dict):
            if "parts" not in last_turn or last_turn["parts"] is None:
                last_turn["parts"] = []
            last_turn["parts"].extend(p_list)
    else:
        history.append(types.Content(role=role, parts=p_list))

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
        self.memory = MemoryManager(max_history=getattr(args, 'max_history', 10))
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
        safe_append_to_history(agent.history, "user", [types.Part(text=self.last_interaction)])
        agent.history = clean_history(agent.history)
        
        session_file = getattr(self.args, 'save_file', 'swarm_session.json')
        
        while True:
            try:
                decls = [ToolRegistry.get_all_definitions()[t] for t in agent.tools_enabled if t in ToolRegistry.get_all_definitions()]
                active_tools = [{"function_declarations": decls}] if decls else None
                
                config = types.GenerateContentConfig(system_instruction=self._build_root_prompt(agent), tools=active_tools if active_tools else None)
                resp = self.client.models.generate_content(model=agent.model, config=config, contents=clean_history(agent.history))
                
                candidate = resp.candidates[0]
                current_chunk = "".join([p.text for p in candidate.content.parts if p.text])
                if current_chunk:
                    if full_output_text:
                        full_output_text += "\n" + current_chunk
                    else:
                        full_output_text = current_chunk

                calls = [p.function_call for p in candidate.content.parts if p.function_call]
                
                if not calls:
                    safe_append_to_history(agent.history, "model", candidate.content.parts)
                    agent.history = clean_history(agent.history)
                    self.last_interaction = full_output_text
                    return full_output_text.strip(), reports

                safe_append_to_history(agent.history, "model", candidate.content.parts)
                tool_results = []
                extra_parts = []
                
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
                    call_id = getattr(call, "id", None)
                    if call_id:
                        tool_results.append(types.Part(function_response=types.FunctionResponse(name=call.name, response={"result": str(res)}, id=call_id)))
                    else:
                        tool_results.append(types.Part.from_function_response(name=call.name, response={"result": str(res)}))
                        
                    if getattr(res, "extra_parts", None):
                        extra_parts.extend(res.extra_parts)
                        
                    reports.append(f"Shared Report: {agent.name} used {call.name}. Output: {str(res)[:150]}...")

                # Append tool results and extra parts into a single user turn
                safe_append_to_history(agent.history, "user", tool_results + extra_parts)
                agent.history = clean_history(agent.history)
                
                if self.turn_passed_manually:
                    if not full_output_text.strip():
                        full_output_text = f"Turn passed to {self.agents[self.current_agent_idx].name}."
                    self.last_interaction = full_output_text
                    return full_output_text.strip(), reports

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

    def inject_message(self, msg, targets=None):
        """
        Injects a message into the session.
        If targets is None or empty, the message is injected globally (sets self.last_interaction,
        and safely appends to the current agent's history).
        If targets is specified (string of comma-separated Names/IDs), it parses and appends
        the message directly to those agents' histories, and switches the current agent
        to the first matched agent.
        """
        if not msg:
            return "Error: Cannot inject empty message."
            
        if not targets:
            self.last_interaction = msg
            curr_agent = self.agents[self.current_agent_idx]
            safe_append_to_history(curr_agent.history, "user", [types.Part(text=msg)])
            curr_agent.history = clean_history(curr_agent.history)
            return f"Message injected globally to current agent ({curr_agent.name})."
            
        target_list = [t.strip().lower() for t in targets.split(",") if t.strip()]
        matched_agents = []
        for t in target_list:
            for i, a in enumerate(self.agents):
                if str(a.id) == t or a.name.lower() == t:
                    if (i, a) not in matched_agents:
                        matched_agents.append((i, a))
                        
        if not matched_agents:
            return f"No agents matched the targets: '{targets}'"
            
        for idx, agent in matched_agents:
            safe_append_to_history(agent.history, "user", [types.Part(text=msg)])
            agent.history = clean_history(agent.history)
            
        first_idx, first_agent = matched_agents[0]
        self.current_agent_idx = first_idx
        self.last_interaction = msg
        names = ", ".join([a.name for _, a in matched_agents])
        return f"Message injected to agent(s): {names}. Current agent switched to {first_agent.name}."

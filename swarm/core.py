import logging
from google import genai
from google.genai import types
from .utils import Colors, Serializer
from .tools import ToolRegistry

logger = logging.getLogger("Swarm.Core")

class Agent:
    def __init__(self, agent_id, name, description, config):
        self.id = agent_id
        self.name = name
        self.description = description
        self.model = config.get('model', 'gemini-3.1-flash-lite')
        self.sys_prompt = config.get('sys_prompt', 'You are a helpful agent.')
        self.temperature = config.get('temp', 0.7)
        self.history = []
        self.tools_enabled = config.get('tools', ["web_search", "shell_exec", "upload_file", "pass_turn"])
        self.max_search = config.get('max_search', 5)
        self.cmd_timeout = config.get('cmd_timeout', 300)
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
        self.last_interaction = args.first_msg
        self.enable_pauses = not args.no_pause
        self.turn_passed_manually = False
        self._init_agents(args)

    def _init_agents(self, args):
        arg_dict = vars(args)
        for i in range(args.agents_count):
            p = f"ai{i+1}_"
            config = {
                'model': arg_dict.get(f"{p}model", args.model),
                'sys_prompt': arg_dict.get(f"{p}sys", args.sys1 if i == 0 else args.sys2),
                'temp': arg_dict.get(f"{p}temp", args.temp),
                'tools': arg_dict.get(f"{p}tools", ["web_search", "shell_exec", "upload_file", "pass_turn"]),
                'max_search': int(arg_dict.get(f"{p}max_search", args.max_results)),
                'cmd_timeout': int(arg_dict.get(f"{p}cmd_timeout", args.cmd_timeout)),
                'cmd_blacklist': arg_dict.get(f"{p}cmd_blacklist", args.cmd_blacklist),
                'file_blacklist': arg_dict.get(f"{p}file_blacklist", args.file_blacklist),
            }
            name = arg_dict.get(f"{p}name", f"Agent_{i+1}")
            desc = arg_dict.get(f"{p}desc", "A Swarm Agent.")
            self.agents.append(Agent(i+1, name, desc, config))

    def rotate_key(self):
        if len(self.keys) > 1:
            self.key_idx = (self.key_idx + 1) % len(self.keys)
            self.client = genai.Client(api_key=self.keys[self.key_idx])
            logger.info(f"API key rotated to index {self.key_idx}")
            return True
        return False

    def _build_root_prompt(self, agent):
        swarm_map = "\n".join([f"- {a.name}: {a.description}" for a in self.agents])
        return (f"{agent.sys_prompt}\n\n"
                f"--- SWARM SYSTEM CONTEXT ---\n"
                f"IDENTITY: {agent.name}\n"
                f"AGENTS LIST:\n{swarm_map}\n"
                f"RULES: You are autonomous. If you need info, use tools. "
                f"If you finish your task, use 'pass_turn' to give control to another agent.")

    def execute_step(self):
        agent = self.agents[self.current_agent_idx]
        agent.history.append(types.Content(role="user", parts=[types.Part(text=self.last_interaction)]))
        
        full_text = ""
        reports = []
        self.turn_passed_manually = False

        while True:
            try:
                decls = []
                if "web_search" in agent.tools_enabled:
                    decls.append({"name": "web_search", "description": "Search web", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}})
                if "shell_exec" in agent.tools_enabled:
                    decls.append({"name": "shell_exec", "description": "Run bash", "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}})
                if "upload_file" in agent.tools_enabled:
                    decls.append({"name": "upload_file", "description": "Upload file", "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]}})
                if "pass_turn" in agent.tools_enabled and len(self.agents) > 1:
                    decls.append({"name": "pass_turn", "description": "Pass turn to agent", "parameters": {"type": "OBJECT", "properties": {"agent_name": {"type": "STRING"}}, "required": ["agent_name"]}})
                
                tools = [{"function_declarations": decls}] if decls else None
                config = types.GenerateContentConfig(
                    system_instruction=self._build_root_prompt(agent),
                    tools=tools, temperature=agent.temperature,
                    safety_settings=[types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                )

                resp = self.client.models.generate_content(model=agent.model, config=config, contents=agent.history)
                if not resp.candidates: return "[Blocked by Safety Filters]", []

                candidate = resp.candidates[0]
                chunk = "".join([p.text for p in candidate.content.parts if p.text])
                full_text += chunk

                calls = [p.function_call for p in candidate.content.parts if p.function_call]
                if not calls:
                    agent.history.append(candidate.content)
                    self.last_interaction = full_text
                    return full_text.strip(), reports

                agent.history.append(candidate.content)
                res_parts = []
                for call in calls:
                    fn, args = call.name, call.args
                    res = ""
                    if fn == "pass_turn":
                        target = args.get("agent_name")
                        for i, a in enumerate(self.agents):
                            if a.name == target:
                                self.current_agent_idx = i
                                self.turn_passed_manually = True
                                res = f"Turn passed to {target}."
                                break
                        else: res = f"Error: Agent {target} not found."
                    elif fn == "web_search": res = ToolRegistry.web_search(args.get("query"), agent.max_search)
                    elif fn == "shell_exec": res = ToolRegistry.shell_exec(args.get("command"), agent.cmd_timeout, agent.cmd_blacklist)
                    elif fn == "upload_file":
                        up = ToolRegistry.upload_file(self.client, args.get("path"), agent.file_blacklist)
                        if "uri" in up:
                            res = f"File uploaded to {up['uri']}"
                            agent.history.append(types.Content(role="user", parts=[types.Part(file_data=types.FileData(file_uri=up['uri'], mime_type=up['mime']))]))
                        else: res = f"Error: {up.get('error')}"
                    
                    res_parts.append(types.Part.from_function_response(name=fn, response={"result": res}))
                    reports.append(f"Tool: {agent.name} -> {fn}. Output: {str(res)[:120]}...")

                agent.history.append(types.Content(role="tool", parts=res_parts))
            except Exception as e:
                if "429" in str(e) and self.rotate_key(): continue
                logger.error(f"Execution error: {e}")
                return f"Error: {e}", []

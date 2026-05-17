import logging
from google import genai
from google.genai import types
from .utils import Colors, Serializer
from .tools import ToolRegistry

logger = logging.getLogger("Swarm.Core")

class Agent:
    """Individual Agent state and configuration."""
    def __init__(self, agent_id, name, description, config):
        self.id = agent_id
        self.name = name
        self.description = description
        self.model = config.get('model', 'gemini-3.1-flash-lite')
        self.sys_prompt = config.get('sys_prompt', 'You are a helpful agent.')
        self.temperature = config.get('temp', 0.7)
        self.history = []
        
        # Tool specifics for this agent
        self.tools_enabled = config.get('tools', ["web_search", "shell_exec", "upload_file", "pass_turn"])
        self.max_search = config.get('max_search', 5)
        self.cmd_timeout = config.get('cmd_timeout', 300)
        self.cmd_blacklist = config.get('cmd_blacklist', [])
        self.file_blacklist = config.get('file_blacklist', [])

class SwarmSession:
    """Manager of the multi-agent ReAct loop."""
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
        for i in range(args.agents_count):
            p = f"ai{i+1}_"
            # Get values with fallbacks to global args
            config = {
                'model': getattr(args, f"{p}model", args.model),
                'sys_prompt': getattr(args, f"{p}sys", args.sys1 if i == 0 else args.sys2),
                'temp': getattr(args, f"{p}temp", args.temp),
                'tools': getattr(args, f"{p}tools", ["web_search", "shell_exec", "upload_file", "pass_turn"]),
                'max_search': getattr(args, f"{p}max_search", args.max_results),
                'cmd_timeout': getattr(args, f"{p}cmd_timeout", args.cmd_timeout),
                'cmd_blacklist': getattr(args, f"{p}cmd_blacklist", args.cmd_blacklist),
                'file_blacklist': getattr(args, f"{p}file_blacklist", args.file_blacklist),
            }
            name = getattr(args, f"{p}name", f"Agent_{i+1}")
            desc = getattr(args, f"{p}desc", "A Swarm Agent.")
            self.agents.append(Agent(i+1, name, desc, config))

    def rotate_key(self):
        if len(self.keys) > 1:
            self.key_idx = (self.key_idx + 1) % len(self.keys)
            self.client = genai.Client(api_key=self.keys[self.key_idx])
            logger.info(f"API key rotated to index {self.key_idx}")
            return True
        return False

    def build_system_instruction(self, agent):
        """Constructs the root prompt for the agent."""
        swarm_map = "\n".join([f"- {a.name} (ID: {a.id}): {a.description}" for a in self.agents])
        root = (
            f"{agent.sys_prompt}\n\n"
            f"FRAMEWORK: SWARM\n"
            f"YOUR IDENTITY: {agent.name}\n"
            f"ALL AGENTS IN SWARM:\n{swarm_map}\n\n"
            f"GUIDELINES:\n"
            f"1. You are autonomous. Use tools as needed.\n"
        )
        if len(self.agents) > 1:
            root += "2. You can use 'pass_turn' to give control to another agent by their name.\n"
        else:
            root += "2. You are talking directly to the User.\n"
        return root

    def get_tool_definitions(self, agent):
        decls = []
        if "web_search" in agent.tools_enabled:
            decls.append({"name": "web_search", "description": "Search the web.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}})
        if "shell_exec" in agent.tools_enabled:
            decls.append({"name": "shell_exec", "description": "Execute terminal commands.", "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}})
        if "upload_file" in agent.tools_enabled:
            decls.append({"name": "upload_file", "description": "Upload a local file for analysis.", "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]}})
        if "pass_turn" in agent.tools_enabled and len(self.agents) > 1:
            decls.append({"name": "pass_turn", "description": "Transfer turn to another agent.", "parameters": {"type": "OBJECT", "properties": {"agent_name": {"type": "STRING"}}, "required": ["agent_name"]}})
        return [{"function_declarations": decls}] if decls else None

    def execute_react_step(self):
        """Runs the ReAct loop for the current agent."""
        agent = self.agents[self.current_agent_idx]
        agent.history.append(types.Content(role="user", parts=[types.Part(text=self.last_interaction)]))
        
        full_text_output = ""
        reports = []
        self.turn_passed_manually = False

        while True:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=self.build_system_instruction(agent),
                    tools=self.get_tool_definitions(agent),
                    temperature=agent.temperature,
                    safety_settings=[types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in [
                        "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                )

                response = self.client.models.generate_content(model=agent.model, config=config, contents=agent.history)
                
                if not response.candidates:
                    return "[Blocked by Safety Filters]", []

                candidate = response.candidates[0]
                chunk_text = "".join([p.text for p in candidate.content.parts if p.text])
                full_text_output += chunk_text

                calls = [p.function_call for p in candidate.content.parts if p.function_call]
                
                if not calls:
                    agent.history.append(candidate.content)
                    self.last_interaction = full_text_output
                    return full_text_output, reports

                agent.history.append(candidate.content)
                res_parts = []
                
                for call in calls:
                    fn, args = call.name, call.args
                    logger.info(f"Agent {agent.name} calls tool: {fn}")
                    
                    if fn == "pass_turn":
                        target = args.get("agent_name")
                        for i, a in enumerate(self.agents):
                            if a.name == target:
                                self.current_agent_idx = i
                                self.turn_passed_manually = True
                                res = f"Turn successfully passed to {target}."
                                break
                        else: res = f"Error: Agent '{target}' not found in Swarm."
                    elif fn == "web_search":
                        res = ToolRegistry.web_search(args.get("query"), max_results=agent.max_search)
                    elif fn == "shell_exec":
                        res = ToolRegistry.shell_exec(args.get("command"), timeout=agent.cmd_timeout, blacklist=agent.cmd_blacklist)
                    elif fn == "upload_file":
                        up = ToolRegistry.upload_file(self.client, args.get("path"), blacklist=agent.file_blacklist)
                        if "uri" in up:
                            res = f"File {args.get('path')} uploaded to {up['uri']}"
                            agent.history.append(types.Content(role="user", parts=[types.Part(file_data=types.FileData(file_uri=up['uri'], mime_type=up['mime']))]))
                        else: res = f"File Upload Error: {up.get('error')}"
                    
                    res_parts.append(types.Part.from_function_response(name=fn, response={"result": res}))
                    reports.append(f"Tool Report: {agent.name} -> {fn}. Result: {str(res)[:150]}...")

                agent.history.append(types.Content(role="tool", parts=res_parts))

            except Exception as e:
                if "429" in str(e) and self.rotate_key(): continue
                logger.error(f"Cycle Exception: {e}")
                return f"Error during agent cycle: {e}", []

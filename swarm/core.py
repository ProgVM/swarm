import logging
from google import genai
from google.genai import types
from .utils import Colors, Serializer
from .tools import ToolRegistry

logger = logging.getLogger("Swarm.Core")

class Agent:
    """Represents a single autonomous entity within the Swarm."""
    def __init__(self, agent_id, name, description, config):
        self.id = agent_id
        self.name = name
        self.description = description
        self.model = config.get('model', 'gemini-3.1-flash-lite')
        self.sys_prompt = config.get('sys_prompt', 'You are a helpful agent.')
        self.temperature = float(config.get('temp', 0.7))
        self.history = []
        
        # Agent-specific tool configuration
        self.tools_enabled = config.get('tools', ["web_search", "shell_exec", "upload_file", "pass_turn"])
        self.max_search = int(config.get('max_search', 5))
        self.cmd_timeout = int(config.get('cmd_timeout', 300))
        self.cmd_blacklist = config.get('cmd_blacklist', [])
        self.file_blacklist = config.get('file_blacklist', [])

class SwarmSession:
    """Manages the collaboration environment and turn-taking logic."""
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
        """Parses arguments to build individual agent profiles."""
        arg_dict = vars(args)
        for i in range(args.agents_count):
            p = f"ai{i+1}_"
            # Hierarchy: aiN_specific_flag > global_flag > default
            config = {
                'model': arg_dict.get(f"{p}model", args.model),
                'sys_prompt': arg_dict.get(f"{p}sys", args.sys1 if i == 0 else args.sys2),
                'temp': arg_dict.get(f"{p}temp", args.temp),
                'tools': arg_dict.get(f"{p}tools", ["web_search", "shell_exec", "upload_file", "pass_turn"]),
                'max_search': arg_dict.get(f"{p}max_search", args.max_results),
                'cmd_timeout': arg_dict.get(f"{p}cmd_timeout", args.cmd_timeout),
                'cmd_blacklist': arg_dict.get(f"{p}cmd_blacklist", args.cmd_blacklist),
                'file_blacklist': arg_dict.get(f"{p}file_blacklist", args.file_blacklist),
            }
            name = arg_dict.get(f"{p}name", f"Agent_{i+1}")
            desc = arg_dict.get(f"{p}desc", "An autonomous participant in the Swarm.")
            self.agents.append(Agent(i+1, name, desc, config))

    def rotate_key(self):
        """Switches to the next available API key in case of quota exhaustion."""
        if len(self.keys) > 1:
            self.key_idx = (self.key_idx + 1) % len(self.keys)
            self.client = genai.Client(api_key=self.keys[self.key_idx])
            logger.info(f"Rotating API keys. Active key index: {self.key_idx}")
            return True
        return False

    def _build_root_prompt(self, agent):
        """Dynamic system prompt providing the agent with swarm awareness."""
        swarm_map = "\n".join([f"- {a.name} (ID: {a.id}): {a.description}" for a in self.agents])
        return (f"{agent.sys_prompt}\n\n"
                f"--- SWARM ARCHITECTURE ---\n"
                f"YOUR NAME: {agent.name}\n"
                f"PARTICIPANTS:\n{swarm_map}\n\n"
                f"RULES:\n"
                f"1. You have tools to search, run code, and analyze files.\n"
                f"2. Use 'pass_turn' to hand over control to another agent specifically.\n"
                f"3. All tool results are broadcasted to other agents automatically.")

    def execute_step(self):
        """
        Runs the ReAct (Reasoning + Acting) cycle for the active agent.
        Will continue looping if the agent invokes tools.
        """
        agent = self.agents[self.current_agent_idx]
        agent.history.append(types.Content(role="user", parts=[types.Part(text=self.last_interaction)]))
        
        full_output_text = ""
        reports = []
        self.turn_passed_manually = False

        while True:
            try:
                # Prepare dynamic tool specifications
                decls = []
                if "web_search" in agent.tools_enabled:
                    decls.append({"name": "web_search", "description": "Search the web.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]}})
                if "shell_exec" in agent.tools_enabled:
                    decls.append({"name": "shell_exec", "description": "Run bash commands.", "parameters": {"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]}})
                if "upload_file" in agent.tools_enabled:
                    decls.append({"name": "upload_file", "description": "Upload local file.", "parameters": {"type": "OBJECT", "properties": {"path": {"type": "STRING"}}, "required": ["path"]}})
                if "pass_turn" in agent.tools_enabled and len(self.agents) > 1:
                    decls.append({"name": "pass_turn", "description": "Delegate to peer.", "parameters": {"type": "OBJECT", "properties": {"agent_name": {"type": "STRING"}}, "required": ["agent_name"]}})
                
                tools = [{"function_declarations": decls}] if decls else None
                config = types.GenerateContentConfig(
                    system_instruction=self._build_root_prompt(agent),
                    tools=tools, 
                    temperature=agent.temperature,
                    safety_settings=[types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in [
                        "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                )

                resp = self.client.models.generate_content(model=agent.model, config=config, contents=agent.history)
                
                if not resp.candidates:
                    return "[Blocked by AI Safety Filters]", []

                candidate = resp.candidates[0]
                # Accumulate text chunks from the model
                current_chunk = "".join([p.text for p in candidate.content.parts if p.text])
                full_output_text += current_chunk

                # Check for tool calls
                calls = [p.function_call for p in candidate.content.parts if p.function_call]
                
                if not calls:
                    # Final textual response reached
                    agent.history.append(candidate.content)
                    self.last_interaction = full_output_text
                    return full_output_text.strip(), reports

                # Add model's thought (call) to history
                agent.history.append(candidate.content)
                tool_results = []
                
                for call in calls:
                    fn, args = call.name, call.args
                    logger.info(f"Agent {agent.name} invokes {fn}")
                    
                    if fn == "pass_turn":
                        target = args.get("agent_name")
                        for i, a in enumerate(self.agents):
                            if a.name == target:
                                self.current_agent_idx = i
                                self.turn_passed_manually = True
                                res_val = f"System: Turn successfully passed to {target}."
                                break
                        else: res_val = f"System Error: Agent '{target}' not found."
                    elif fn == "web_search":
                        res_val = ToolRegistry.web_search(args.get("query"), agent.max_search)
                    elif fn == "shell_exec":
                        res_val = ToolRegistry.shell_exec(args.get("command"), agent.cmd_timeout, agent.cmd_blacklist)
                    elif fn == "upload_file":
                        up = ToolRegistry.upload_file(self.client, args.get("path"), agent.file_blacklist)
                        if "uri" in up:
                            res_val = f"System: File uploaded to {up['uri']}"
                            # Inject FileData so the model can actually "see" the file content
                            agent.history.append(types.Content(
                                role="user", 
                                parts=[types.Part(file_data=types.FileData(file_uri=up['uri'], mime_type=up['mime']))]
                            ))
                        else: res_val = f"System Error: {up.get('error')}"
                    
                    tool_results.append(types.Part.from_function_response(name=fn, response={"result": res_val}))
                    reports.append(f"Shared Report: {agent.name} used {fn}. Output: {str(res_val)[:150]}...")

                # Add execution results to history and continue loop
                agent.history.append(types.Content(role="tool", parts=tool_results))

            except Exception as e:
                if "429" in str(e) and self.rotate_key():
                    continue
                logger.error(f"Agent Cycle Error: {e}")
                return f"Internal Framework Error: {e}", []

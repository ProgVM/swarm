import argparse
import os
import json
import logging
import sys
from google.genai import types

from .utils import Colors, setup_logger, smart_sleep, Serializer, create_backup
from .config import ConfigManager
from .ui import handle_session_error
from .core import SwarmSession
from .exceptions import SwarmDataError

def parse_args():
    parser = argparse.ArgumentParser(description="Swarm Intelligence Framework")
    parser.add_argument("--agents_count", type=int, default=2)
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--first_msg", default="System start. Greet the participants.")
    parser.add_argument("--keys", nargs="+")
    parser.add_argument("--config", help="JSON Configuration file")
    parser.add_argument("--load", help="Load session state from JSON")
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--no_pause", action="store_true")
    parser.add_argument("--save_file", default="swarm_session.json")
    parser.add_argument("--max_results", type=int, default=5)
    parser.add_argument("--cmd_timeout", type=int, default=300)
    parser.add_argument("--cmd_blacklist", nargs="*", default=[])
    parser.add_argument("--file_blacklist", nargs="*", default=[])
    parser.add_argument("--sys1", default="You are Agent 1.")
    parser.add_argument("--sys2", default="You are Agent 2.")
    parser.add_argument("--temp", type=float, default=0.7)
    return parser.parse_known_args()

def run():
    args, unknown = parse_args()
    it = iter(unknown)
    for item in it:
        if item.startswith("--"):
            key = item.lstrip("-")
            try:
                val = next(it)
                try: val = json.loads(val)
                except: pass
                setattr(args, key, val)
            except StopIteration:
                setattr(args, key, True)

    logger = setup_logger(args.log_level)
    
    # Defaults layer
    defaults = {
        "agents_count": 2,
        "model": "gemini-3.1-flash-lite",
        "first_msg": "System start. Greet the participants.",
        "log_level": "INFO",
        "no_pause": False,
        "save_file": "swarm_session.json",
        "max_results": 5,
        "cmd_timeout": 300,
        "cmd_blacklist": [],
        "file_blacklist": [],
        "sys1": "You are Agent 1.",
        "sys2": "You are Agent 2.",
        "temp": 0.7
    }

    # Load file config if passed via --config
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            conf_file = json.load(f)
            for k, v in conf_file.items():
                if not hasattr(args, k): setattr(args, k, v)

    # Load session configuration layer if restoring state
    session_config = {}
    if args.load and os.path.exists(args.load):
        try:
            with open(args.load, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
                session_config = state_data.get("config", {})
        except Exception:
            pass

    # Filter cli args to preserve layers hierarchy
    cli_args = {k: v for k, v in vars(args).items() if v is not None}

    # Unified layered merge using ConfigManager (defaults <- session_config <- cli_args)
    merged_config = ConfigManager.merge(defaults, session_config, cli_args)

    class ConfigNamespace:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)
                
    args = ConfigNamespace(merged_config)

    keys = args.keys or [os.getenv("GOOGLE_API_KEY")]
    if not keys or not keys[0]:
        print(f"{Colors.ERR}CRITICAL: No API Keys found.{Colors.RESET}")
        return

    session = SwarmSession(args, keys)

    if args.load:
        try:
            state = session.load_and_validate(args.load)
            for i, hist in enumerate(state.get("histories", [])):
                if i < len(session.agents):
                    session.agents[i].history = Serializer.deserialize_history(hist)
            print(f"{Colors.SYS}Swarm state restored successfully.{Colors.RESET}")
        except SwarmDataError as e:
            if handle_session_error(e):
                sys.exit(1)

    print(f"{Colors.SYS}{Colors.BOLD}>>> SWARM INITIALIZED.{Colors.RESET}")

    while True:
        try:
            agent = session.agents[session.current_agent_idx]
            color = Colors.AI_COLORS[session.current_agent_idx % len(Colors.AI_COLORS)]

            if args.agents_count == 1 and len(agent.history) > 0:
                user_msg = input(f"{Colors.BOLD}User: {Colors.RESET}")
                session.last_interaction = user_msg

            response, reports = session.execute_step()
            
            for rep in reports:
                print(f"{Colors.REPORT}{rep}{Colors.RESET}")
                for other in session.agents:
                    if other != agent:
                        other.history.append(types.Content(role="user", parts=[types.Part(text=f"[SYSTEM REPORT] {rep}")]))

            print(f"{color}{Colors.BOLD}{agent.name}:{Colors.RESET} {response}")

            if not session.turn_passed_manually and args.agents_count > 1:
                session.current_agent_idx = (session.current_agent_idx + 1) % args.agents_count

            delay = (len(response) / 12) * 1.5
            smart_sleep(max(3.5, min(delay, 35)), enabled=session.enable_pauses)

        except KeyboardInterrupt:
            print(f"\n{Colors.MENU}{Colors.BOLD}=== COMMAND CENTER ==={Colors.RESET}")
            print("1. Rotate Keys\n2. Toggle Pauses\n3. Save State\n4. Inject Message\n5. Log Level\n6. Shutdown")
            choice = input(f"{Colors.MENU}Command: {Colors.RESET}").strip()
            
            if choice == '1': 
                session.rotate_key()
            elif choice == '2': 
                session.enable_pauses = not session.enable_pauses
            elif choice == '3':
                p = input(f"File path [{args.save_file}]: ") or args.save_file
                create_backup(p)
                
                # Filter out sensitive credentials before saving config
                saved_config = vars(args).copy()
                if "keys" in saved_config:
                    del saved_config["keys"]

                save_data = {
                    "current_agent": session.current_agent_idx,
                    "last_interaction": session.last_interaction,
                    "histories": [Serializer.serialize_history(a.history) for a in session.agents],
                    "version": "1.0",
                    "config": saved_config
                }
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=2, ensure_ascii=False)
                print(f"State saved to {p}")
            elif choice == '6': 
                sys.exit(0)

if __name__ == "__main__":
    run()

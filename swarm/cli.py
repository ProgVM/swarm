import argparse
import os
import json
import logging
import sys
from google.genai import types

from .utils import Colors, setup_logger, smart_sleep, Serializer, create_backup, get_turn_role, get_turn_parts
from .config import ConfigManager
from .ui import handle_session_error
from .core import SwarmSession, safe_append_to_history, clean_history
from .exceptions import SwarmDataError, SwarmConfigError
from .locking import SessionLockManager

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
    parser.add_argument("--max_history", type=int, default=10)
    parser.add_argument("--cmd_blacklist", nargs="*", default=[])
    parser.add_argument("--file_blacklist", nargs="*", default=[])
    parser.add_argument("--sys1", default="You are Agent 1.")
    parser.add_argument("--sys2", default="You are Agent 2.")
    parser.add_argument("--temp", type=float, default=0.7)
    parser.add_argument("--inject_msg", help="Message to inject upon startup")
    parser.add_argument("--inject_targets", help="Target agent(s) (Names or IDs, comma-separated) for injected message")
    return parser.parse_known_args()

def run():
    try:
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
    except Exception as e:
        print(f"CRITICAL: Failed to parse arguments or initialize logger: {e}")
        sys.exit(1)
    
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
        "max_history": 10,
        "cmd_blacklist": [],
        "file_blacklist": [],
        "sys1": "You are Agent 1.",
        "sys2": "You are Agent 2.",
        "temp": 0.7,
        "keys": None,
        "config": None,
        "load": None,
        "inject_msg": os.getenv("SWARM_INJECT_MSG"),
        "inject_targets": os.getenv("SWARM_INJECT_TARGETS")
    }

    try:
        # Load file config if passed via --config
        if args.config:
            if not os.path.exists(args.config):
                raise SwarmConfigError(f"Config file not found: {args.config}")
            try:
                with open(args.config, 'r', encoding='utf-8') as f:
                    conf_file = json.load(f)
            except json.JSONDecodeError as e:
                raise SwarmConfigError(f"Config file is not valid JSON: {e}")
            except Exception as e:
                raise SwarmConfigError(f"Failed to read config file: {e}")
                
            for k, v in conf_file.items():
                if not hasattr(args, k): setattr(args, k, v)

        # Load session configuration layer if restoring state
        session_config = {}
        if args.load:
            if not os.path.exists(args.load):
                raise SwarmConfigError(f"Session load file not found: {args.load}")
            try:
                with open(args.load, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    session_config = state_data.get("config", {})
            except json.JSONDecodeError as e:
                raise SwarmConfigError(f"Session load file is not valid JSON: {e}")
            except Exception as e:
                raise SwarmConfigError(f"Failed to read session load file: {e}")

        # Filter cli args to preserve layers hierarchy
        cli_args = {k: v for k, v in vars(args).items() if v is not None}

        # Unified layered merge using ConfigManager (defaults <- session_config <- cli_args)
        merged_config = ConfigManager.merge(defaults, session_config, cli_args)

        # Run validations on merged configuration
        ConfigManager.validate(merged_config)
    except SwarmConfigError as e:
        print(f"{Colors.ERR}CONFIGURATION ERROR: {e}{Colors.RESET}")
        sys.exit(1)

    class ConfigNamespace:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)
        def __getattr__(self, item):
            return None
                
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

    if args.inject_msg:
        print(f"{Colors.SYS}Executing startup message injection...{Colors.RESET}")
        res_msg = session.inject_message(args.inject_msg, args.inject_targets)
        print(f"{Colors.SYS}{res_msg}{Colors.RESET}")

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
                        safe_append_to_history(other.history, "user", [types.Part(text=f"[SYSTEM REPORT] {rep}")])
                        other.history = clean_history(other.history)

            print(f"{color}{Colors.BOLD}{agent.name}:{Colors.RESET} {response}")

            if not session.turn_passed_manually and args.agents_count > 1:
                session.current_agent_idx = (session.current_agent_idx + 1) % args.agents_count

            delay = (len(response) / 12) * 1.5
            smart_sleep(max(3.5, min(delay, 35)), enabled=session.enable_pauses)

        except KeyboardInterrupt:
            try:
                print(f"\n{Colors.MENU}{Colors.BOLD}=== COMMAND CENTER ==={Colors.RESET}")
                print("1. Rotate Keys\n2. Toggle Pauses\n3. Save State\n4. Inject Message\n5. Log Level")
                print("6. List Agents & Status\n7. Switch Current Agent\n8. View Agent History\n9. Shutdown")
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
                    with SessionLockManager.atomic_update(p) as session_data:
                        session_data.update(save_data)
                    print(f"State saved to {p}")
                elif choice == '4':
                    print(f"\n{Colors.SYS}--- Message Injection ---{Colors.RESET}")
                    print("Current Agents:")
                    for a in session.agents:
                        last_role = get_turn_role(a.history[-1]) if a.history else "None"
                        print(f"  [{a.id}] {a.name} (Last turn: {last_role})")
                    
                    targets = input("Target agent(s) (IDs or Names, comma-separated, or press Enter for ALL): ").strip()
                    msg = input("Enter message to inject: ").strip()
                    
                    if msg:
                        res_msg = session.inject_message(msg, targets if targets else None)
                        print(f"{Colors.SYS}{res_msg}{Colors.RESET}")
                elif choice == '5':
                    level = input("Enter log level (DEBUG, INFO, WARNING, ERROR): ").strip().upper()
                    if level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                        logging.getLogger().setLevel(getattr(logging, level))
                        print(f"Log level changed to {level}")
                elif choice == '6':
                    print(f"\n{Colors.SYS}=== AGENTS STATUS ==={Colors.RESET}")
                    for i, a in enumerate(session.agents):
                        is_current = " (ACTIVE)" if i == session.current_agent_idx else ""
                        print(f"[{a.id}] {a.name}{is_current}:")
                        print(f"  Model: {a.model}")
                        print(f"  Description: {a.description}")
                        print(f"  History turns: {len(a.history)}")
                elif choice == '7':
                    print("\nSelect agent to activate:")
                    for i, a in enumerate(session.agents):
                        print(f"  [{i}] {a.name}")
                    idx_str = input("Enter index: ").strip()
                    if idx_str.isdigit():
                        idx = int(idx_str)
                        if 0 <= idx < len(session.agents):
                            session.current_agent_idx = idx
                            print(f"Activated agent: {session.agents[idx].name}")
                        else:
                            print("Invalid index.")
                elif choice == '8':
                    print("\nSelect agent to view history:")
                    for i, a in enumerate(session.agents):
                        print(f"  [{i}] {a.name}")
                    idx_str = input("Enter index: ").strip()
                    if idx_str.isdigit():
                        idx = int(idx_str)
                        if 0 <= idx < len(session.agents):
                            print(f"\n--- History of {session.agents[idx].name} ---")
                            for j, turn in enumerate(session.agents[idx].history):
                                role = get_turn_role(turn)
                                parts = get_turn_parts(turn)
                                print(f"Turn {j+1} [{role}]:")
                                for p in parts:
                                    if hasattr(p, "text") and p.text:
                                        print(f"  {p.text[:200]}")
                                    elif hasattr(p, "function_call") and p.function_call:
                                        print(f"  Function Call: {p.function_call.name}")
                                    elif hasattr(p, "function_response") and p.function_response:
                                        print(f"  Function Response: {p.function_response.name}")
                                    elif isinstance(p, dict):
                                        print(f"  Dict Part: {str(p)[:200]}")
                                    else:
                                        print(f"  Other part: {type(p).__name__}")
                elif choice == '9': 
                    sys.exit(0)
            except KeyboardInterrupt:
                print(f"\n{Colors.SYS}Menu cancelled.{Colors.RESET}")


if __name__ == "__main__":
    run()

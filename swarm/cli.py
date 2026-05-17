import argparse
import os
import json
import logging
import sys
from google.genai import types
from .utils import Colors, setup_logger, smart_sleep, Serializer
from .core import SwarmSession

def parse_args():
    """Defines global arguments and prepares for dynamic agent-prefixed flags."""
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
    
    # Global tool defaults
    parser.add_argument("--max_results", type=int, default=5)
    parser.add_argument("--cmd_timeout", type=int, default=300)
    parser.add_argument("--cmd_blacklist", nargs="*", default=[])
    parser.add_argument("--file_blacklist", nargs="*", default=[])
    
    # Fallback prompts
    parser.add_argument("--sys1", default="You are Agent 1.")
    parser.add_argument("--sys2", default="You are Agent 2.")
    parser.add_argument("--temp", type=float, default=0.7)

    return parser.parse_known_args()

def run():
    """Main CLI entry point."""
    args, unknown = parse_args()
    
    # Process dynamic flags (e.g., --ai1_name Architect)
    it = iter(unknown)
    for item in it:
        if item.startswith("--"):
            key = item.lstrip("-")
            try:
                val = next(it)
                # Try to parse as JSON for complex values (lists/dicts)
                try: val = json.loads(val)
                except: pass
                setattr(args, key, val)
            except StopIteration:
                setattr(args, key, True)

    logger = setup_logger(args.log_level)
    
    # Load config file (Overrides defaults, but overridden by CLI args)
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r', encoding='utf-8') as f:
            conf = json.load(f)
            for k, v in conf.items():
                if not hasattr(args, k) or getattr(args, k) == parser.get_default(k):
                    setattr(args, k, v)

    keys = args.keys or [os.getenv("GOOGLE_API_KEY")]
    if not keys or not keys[0]:
        print(f"{Colors.ERR}CRITICAL: No API Keys found. Use --keys or set GOOGLE_API_KEY.{Colors.RESET}")
        return

    # Initialize Swarm Session
    session = SwarmSession(args, keys)

    # Restore session state if requested
    if args.load and os.path.exists(args.load):
        with open(args.load, 'r', encoding='utf-8') as f:
            state = json.load(f)
            session.current_agent_idx = state.get("current_agent", 0)
            session.last_interaction = state.get("last_interaction", args.first_msg)
            for i, hist in enumerate(state.get("histories", [])):
                if i < len(session.agents):
                    session.agents[i].history = Serializer.deserialize_history(hist)
            print(f"{Colors.SYS}Swarm state restored. CLI arguments will apply to new steps.{Colors.RESET}")

    print(f"{Colors.SYS}{Colors.BOLD}>>> SWARM INITIALIZED. CTRL+C FOR COMMAND CENTER.{Colors.RESET}")

    while True:
        try:
            agent = session.agents[session.current_agent_idx]
            color = Colors.AI_COLORS[session.current_agent_idx % len(Colors.AI_COLORS)]

            # 1-Agent User Input Logic
            if args.agents_count == 1 and len(agent.history) > 0:
                user_msg = input(f"{Colors.BOLD}User: {Colors.RESET}")
                session.last_interaction = user_msg

            # Agent Cycle
            response, reports = session.execute_step()
            
            # Print Tool Reports and Synchronize Contexts
            for rep in reports:
                print(f"{Colors.REPORT}{rep}{Colors.RESET}")
                # Broadcast reports to all other agents in the Swarm
                for other in session.agents:
                    if other != agent:
                        other.history.append(types.Content(
                            role="user", 
                            parts=[types.Part(text=f"[SYSTEM REPORT] {rep}")]
                        ))

            # Display Agent Message
            print(f"{color}{Colors.BOLD}{agent.name}:{Colors.RESET} {response}")

            # Turn Rotation Logic (Skip if pass_turn was used)
            if not session.turn_passed_manually and args.agents_count > 1:
                session.current_agent_idx = (session.current_agent_idx + 1) % args.agents_count

            # Inter-turn sleep
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
                print(f"Pauses: {'Enabled' if session.enable_pauses else 'Disabled'}")
            elif choice == '3':
                p = input(f"File path [{args.save_file}]: ") or args.save_file
                save_data = {
                    "current_agent": session.current_agent_idx,
                    "last_interaction": session.last_interaction,
                    "histories": [Serializer.serialize_history(a.history) for a in session.agents]
                }
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=2, ensure_ascii=False)
                print(f"State saved to {p}")
            elif choice == '4':
                target = input("Target Name (or 'all'): ")
                msg = input("Manual Injection: ")
                packet = types.Content(role="user", parts=[types.Part(text=f"[USER DIRECTIVE] {msg}")])
                for a in session.agents:
                    if target.lower() == 'all' or a.name == target:
                        a.history.append(packet)
                print("Injection complete.")
            elif choice == '5':
                lvl = input("New Level (DEBUG, INFO, WARNING): ").upper()
                logging.getLogger("Swarm").setLevel(getattr(logging, lvl, logging.INFO))
            elif choice == '6':
                print("Swarm shutting down...")
                sys.exit(0)

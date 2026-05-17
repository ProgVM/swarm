import argparse
import os
import json
import logging
from .utils import Colors, setup_logger, smart_sleep, Serializer
from .core import SwarmSession

def parse_args():
    parser = argparse.ArgumentParser(description="Swarm Framework")
    parser.add_argument("--agents_count", type=int, default=2)
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--first_msg", default="Initialize Swarm and greet the user.")
    parser.add_argument("--keys", nargs="+")
    parser.add_argument("--config", help="Path to config JSON")
    parser.add_argument("--load", help="Load session JSON")
    parser.add_argument("--log_level", default="INFO")
    parser.add_argument("--no_pause", action="store_true")
    parser.add_argument("--save_file", default="swarm_session.json")
    
    # Global tool settings
    parser.add_argument("--max_results", type=int, default=5)
    parser.add_argument("--cmd_timeout", type=int, default=300)
    parser.add_argument("--cmd_blacklist", nargs="*", default=[])
    parser.add_argument("--file_blacklist", nargs="*", default=[])
    
    # Defaults
    parser.add_argument("--sys1", default="You are Agent 1.")
    parser.add_argument("--sys2", default="You are Agent 2.")
    parser.add_argument("--temp", type=float, default=0.7)

    return parser.parse_known_args()

def run():
    args, unknown = parse_args()
    logger = setup_logger(args.log_level)
    
    # 1. Load config if exists (Overrides defaults)
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            cdata = json.load(f)
            for k, v in cdata.items(): setattr(args, k, v)

    # 2. Collect API Keys
    keys = args.keys or [os.getenv("GOOGLE_API_KEY")]
    if not keys or not keys[0]:
        print(f"{Colors.ERR}Error: API Keys not found. Set GOOGLE_API_KEY environment variable or use --keys.{Colors.RESET}")
        return

    session = SwarmSession(args, keys)

    # 3. Handle loading (Arguments take priority after load)
    if args.load and os.path.exists(args.load):
        with open(args.load, 'r') as f:
            sd = json.load(f)
            session.current_agent_idx = sd.get("current_agent", 0)
            session.last_interaction = sd.get("last_interaction", args.first_msg)
            for i, ah in enumerate(sd.get("histories", [])):
                if i < len(session.agents):
                    session.agents[i].history = Serializer.deserialize_history(ah)
            print(f"{Colors.SYS}Session loaded. Overriding with current CLI parameters...{Colors.RESET}")

    print(f"{Colors.SYS}{Colors.BOLD}>>> SWARM STARTING. CTRL+C FOR COMMAND CENTER.{Colors.RESET}")

    while True:
        try:
            agent = session.agents[session.current_agent_idx]
            color = Colors.AI_COLORS[session.current_agent_idx % len(Colors.AI_COLORS)]

            # 1-Agent User Input Mode
            if args.agents_count == 1 and len(agent.history) > 0:
                user_msg = input(f"{Colors.BOLD}User: {Colors.RESET}")
                session.last_interaction = user_msg

            # Agent Thinking
            response, reports = session.execute_react_step()
            
            # Print and Share Reports
            for rep in reports:
                print(f"{Colors.REPORT}{rep}{Colors.RESET}")
                for i, other in enumerate(session.agents):
                    if i != session.current_agent_idx:
                        other.history.append(types.Content(role="user", parts=[types.Part(text=rep)]))

            # Final Output
            print(f"{color}{Colors.BOLD}{agent.name}:{Colors.RESET} {response}")

            # Turn Management
            if not session.turn_passed_manually and args.agents_count > 1:
                session.current_agent_idx = (session.current_agent_idx + 1) % args.agents_count

            # Timing
            wait = (len(response) / 10) * 1.5
            smart_sleep(max(3, min(wait, 30)), enabled=session.enable_pauses)

        except KeyboardInterrupt:
            print(f"\n{Colors.MENU}{Colors.BOLD}=== SWARM COMMAND CENTER ==={Colors.RESET}")
            print("1. Change Keys\n2. Toggle Pauses\n3. Save State\n4. Change Log Level\n5. Exit Swarm")
            choice = input("Choice: ")
            
            if choice == '1':
                nk = input("Enter keys (space separated): ").split()
                if nk: session.keys = nk; session.key_idx = 0
            elif choice == '2':
                session.enable_pauses = not session.enable_pauses
                print(f"Pauses enabled: {session.enable_pauses}")
            elif choice == '3':
                path = input(f"Save filename [{args.save_file}]: ") or args.save_file
                save_data = {
                    "current_agent": session.current_agent_idx,
                    "last_interaction": session.last_interaction,
                    "histories": [Serializer.serialize_history(a.history) for a in session.agents]
                }
                with open(path, 'w') as f: json.dump(save_data, f, indent=2)
                print(f"State saved to {path}")
            elif choice == '4':
                lv = input("Enter Level (DEBUG, INFO, WARNING): ").upper()
                logger.setLevel(getattr(logging, lv, logging.INFO))
            elif choice == '5':
                break

import argparse
import os
import json
import logging
import sys
from google.genai import types
from .utils import Colors, setup_logger, smart_sleep, Serializer
from .core import SwarmSession

def parse_args():
    parser = argparse.ArgumentParser(description="Swarm Intelligence Framework")
    parser.add_argument("--agents_count", type=int, default=2)
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--first_msg", default="Initialize Swarm session.")
    parser.add_argument("--keys", nargs="+")
    parser.add_argument("--config", help="JSON config file")
    parser.add_argument("--load", help="Session state JSON")
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
    
    # Safe dynamic argument processing
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
    
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            cdata = json.load(f)
            for k, v in cdata.items(): setattr(args, k, v)

    keys = args.keys or [os.getenv("GOOGLE_API_KEY")]
    if not keys or not keys[0]:
        print(f"{Colors.ERR}Error: API Keys missing.{Colors.RESET}")
        return

    session = SwarmSession(args, keys)

    if args.load and os.path.exists(args.load):
        with open(args.load, 'r') as f:
            sd = json.load(f)
            session.current_agent_idx = sd.get("current_agent", 0)
            session.last_interaction = sd.get("last_interaction", args.first_msg)
            for i, ah in enumerate(sd.get("histories", [])):
                if i < len(session.agents):
                    session.agents[i].history = Serializer.deserialize_history(ah)
            print(f"{Colors.SYS}Session loaded.{Colors.RESET}")

    print(f"{Colors.SYS}{Colors.BOLD}>>> SWARM ACTIVE. Ctrl+C for Command Center.{Colors.RESET}")

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

            wait = (len(response) / 11) * 1.4
            smart_sleep(max(3.5, min(wait, 35)), enabled=session.enable_pauses)

        except KeyboardInterrupt:
            print(f"\n{Colors.MENU}{Colors.BOLD}=== SWARM COMMAND CENTER ==={Colors.RESET}")
            print("1. Change Keys\n2. Toggle Pauses\n3. Save State\n4. Inject Directive\n5. Change Log Level\n6. Exit")
            c = input("Choice: ")
            if c == '1':
                nk = input("New keys (space separated): ").split()
                if nk: session.keys = nk; session.key_idx = 0; session.rotate_key()
            elif c == '2':
                session.enable_pauses = not session.enable_pauses
                print(f"Pauses: {session.enable_pauses}")
            elif c == '3':
                path = input(f"Filename [{args.save_file}]: ") or args.save_file
                data = {"current_agent": session.current_agent_idx, "last_interaction": session.last_interaction, "histories": [Serializer.serialize_history(a.history) for a in session.agents]}
                with open(path, 'w') as f: json.dump(data, f, indent=2)
                print(f"Saved to {path}")
            elif c == '4':
                target = input("Target Name (or 'all'): ")
                msg = input("Message: ")
                payload = types.Content(role="user", parts=[types.Part(text=f"[MANUAL INJECTION] {msg}")])
                for a in session.agents:
                    if target.lower() == 'all' or a.name == target: a.history.append(payload)
                print("Directive injected.")
            elif c == '5':
                lv = input("Level (DEBUG, INFO, WARNING): ").upper()
                logging.getLogger("Swarm").setLevel(getattr(logging, lv, logging.INFO))
            elif c == '6': sys.exit(0)

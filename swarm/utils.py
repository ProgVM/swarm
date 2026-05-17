import os
import sys
import json
import time
import select
import logging
from google.genai import types

class Colors:
    """ANSI Escape sequences for professional terminal output."""
    AI_COLORS = ['\033[94m', '\033[92m', '\033[96m', '\033[95m', '\033[91m', '\033[33m']
    SYS = '\033[93m'
    ERR = '\033[91m'
    TOOL = '\033[36m'
    REPORT = '\033[90m'
    MENU = '\033[95m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def setup_logger(level_name="INFO"):
    """Initializes the logging system with configurable levels."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger("Swarm")

def smart_sleep(timeout, enabled=True):
    """Provides a toggleable pause that can be skipped with the Enter key."""
    if not enabled or timeout <= 0:
        return
    print(f"{Colors.REPORT}[Pause: {timeout:.1f}s | Press Enter to skip]{Colors.RESET}", end="", flush=True)
    # Use select for non-blocking stdin check
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if ready:
        sys.stdin.readline()
        print(f"\r{Colors.SYS}[User Skipped Pause]{' ' * 30}{Colors.RESET}")
    else:
        # Clear the line after pause expires
        print(f"\r{' ' * 50}\r", end="", flush=True)

class Serializer:
    """Serializes and deserializes Google GenAI objects for persistent storage."""
    @staticmethod
    def serialize_history(history):
        data = []
        for content in history:
            parts_list = []
            for p in content.parts:
                if p.text:
                    parts_list.append({"text": p.text})
                elif p.function_call:
                    parts_list.append({"function_call": {"name": p.function_call.name, "args": p.function_call.args}})
                elif p.function_response:
                    parts_list.append({"function_response": {"name": p.function_response.name, "response": p.function_response.response}})
                elif p.file_data:
                    parts_list.append({"file_data": {"file_uri": p.file_data.file_uri, "mime_type": p.file_data.mime_type}})
            data.append({"role": content.role, "parts": parts_list})
        return data

    @staticmethod
    def deserialize_history(data):
        history = []
        for item in data:
            parts = []
            for p in item.get('parts', []):
                if "text" in p:
                    parts.append(types.Part(text=p["text"]))
                elif "function_call" in p:
                    fc = p["function_call"]
                    parts.append(types.Part(function_call=types.FunctionCall(name=fc["name"], args=fc["args"])))
                elif "function_response" in p:
                    fr = p["function_response"]
                    parts.append(types.Part.from_function_response(name=fr["name"], response=fr["response"]))
                elif "file_data" in p:
                    fd = p["file_data"]
                    parts.append(types.Part(file_data=types.FileData(file_uri=fd["file_uri"], mime_type=fd["mime_type"])))
            if parts:
                history.append(types.Content(role=item["role"], parts=parts))
        return history

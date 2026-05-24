import logging
import shutil
import os
import json
from swarm.exceptions import SwarmDataError

class Colors:
    SYS = "\033[94m"
    ERR = "\033[91m"
    MENU = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    REPORT = "\033[33m"
    AI_COLORS = ["\033[92m", "\033[95m", "\033[93m"]

def setup_logger(level):
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    return logging.getLogger("Swarm")

def smart_sleep(seconds, enabled=True):
    if enabled:
        import time
        time.sleep(seconds)

def create_backup(filepath):
    """Creates a .bak file of the session before modification."""
    if os.path.exists(filepath):
        shutil.copy(filepath, filepath + ".bak")

class Serializer:
    @staticmethod
    def serialize_history(history):
        return [h.model_dump(mode='json') for h in history]
    
    @staticmethod
    def deserialize_history(history_data):
        from google.genai import types
        return [types.Content(**h) for h in history_data]

def get_turn_role(turn):
    if hasattr(turn, "role"):
        return turn.role
    elif isinstance(turn, dict) and "role" in turn:
        return turn["role"]
    return None

def get_turn_parts(turn):
    if hasattr(turn, "parts"):
        return list(turn.parts) if turn.parts else []
    elif isinstance(turn, dict) and "parts" in turn:
        return list(turn["parts"]) if turn["parts"] else []
    return []

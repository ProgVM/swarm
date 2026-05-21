import json
import datetime
from swarm.locking import SessionLockManager

class EventLogger:
    @staticmethod
    def log_event(file_path, event_type, agent_name, level="INFO", data=None):
        event = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "level": level,
            "event": event_type,
            "agent": agent_name,
            "data": data or {}
        }
        
        # Use atomic_update to ensure thread safety
        with SessionLockManager.atomic_update(file_path) as session_data:
            if "events" not in session_data:
                session_data["events"] = []
            session_data["events"].append(event)

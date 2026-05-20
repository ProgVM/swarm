import json
from swarm.exceptions import SwarmDataError

class SessionValidator:
    @staticmethod
    def validate(data):
        """Strict validation of session data schema."""
        required_keys = {"current_agent", "last_interaction", "histories"}
        if not isinstance(data, dict):
            raise SwarmDataError("Session file must be a JSON object.")
        
        missing = required_keys - data.keys()
        if missing:
            raise SwarmDataError(f"Missing required keys in session file: {missing}")
        
        if not isinstance(data["histories"], list):
            raise SwarmDataError("'histories' must be a list.")
            
        return True

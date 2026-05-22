class MemoryManager:
    def __init__(self, max_history=10):
        self.max_history = max_history

    def manage_history(self, history):
        """
        Implements sliding window. Returns (active_history, archived_history).
        Ensures that the active history always starts with a 'user' turn to avoid
        Gemini's 400 INVALID_ARGUMENT (e.g. 'Please ensure that function call turn
        comes immediately after a user turn or after a function response turn').
        """
        if not history:
            return [], []

        n = len(history)
        split_idx = -1
        
        # 1. Search in the preferred range [n - max_history, n - 1]
        preferred_start = max(0, n - self.max_history)
        for i in range(preferred_start, n):
            item = history[i]
            role = None
            if hasattr(item, "role"):
                role = item.role
            elif isinstance(item, dict):
                role = item.get("role")
                
            if role == "user":
                split_idx = i
                break
                
        # 2. If not found, search backwards from preferred_start - 1 down to 0
        if split_idx == -1:
            for i in range(preferred_start - 1, -1, -1):
                item = history[i]
                role = None
                if hasattr(item, "role"):
                    role = item.role
                elif isinstance(item, dict):
                    role = item.get("role")
                    
                if role == "user":
                    split_idx = i
                    break
                    
        # 3. If we still haven't found any 'user' turn, fall back to index 0
        if split_idx == -1:
            split_idx = 0
            
        if split_idx > 0:
            active = history[split_idx:]
            archived = history[:split_idx]
            return active, archived
            
        return history, []

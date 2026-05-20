class MemoryManager:
    def __init__(self, max_history=10):
        self.max_history = max_history

    def manage_history(self, history):
        """
        Implements sliding window. Returns (active_history, archived_history).
        """
        if len(history) > self.max_history:
            archived = history[:-self.max_history]
            active = history[-self.max_history:]
            return active, archived
        return history, []

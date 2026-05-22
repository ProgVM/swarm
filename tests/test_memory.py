import unittest
from swarm.memory import MemoryManager

class MockTurn:
    def __init__(self, role):
        self.role = role

class TestMemoryManager(unittest.TestCase):
    def test_empty_history(self):
        manager = MemoryManager(max_history=5)
        active, archived = manager.manage_history([])
        self.assertEqual(active, [])
        self.assertEqual(archived, [])

    def test_short_history_starts_with_user(self):
        manager = MemoryManager(max_history=5)
        history = [
            MockTurn("user"),
            MockTurn("model"),
            MockTurn("user")
        ]
        active, archived = manager.manage_history(history)
        self.assertEqual(active, history)
        self.assertEqual(archived, [])

    def test_short_history_starts_with_model(self):
        manager = MemoryManager(max_history=5)
        history = [
            MockTurn("model"),
            MockTurn("user"),
            MockTurn("model")
        ]
        active, archived = manager.manage_history(history)
        # Should discard the first non-user turn
        self.assertEqual([t.role for t in active], ["user", "model"])
        self.assertEqual([t.role for t in archived], ["model"])

    def test_long_history_user_in_preferred_range(self):
        manager = MemoryManager(max_history=5)
        history = [
            MockTurn("user"),  # 0
            MockTurn("model"), # 1
            MockTurn("user"),  # 2
            MockTurn("model"), # 3
            MockTurn("user"),  # 4
            MockTurn("model"), # 5
            MockTurn("user"),  # 6
            MockTurn("model"), # 7
            MockTurn("user"),  # 8
            MockTurn("model")  # 9
        ]
        # max_history = 5. Preferred range is from index 5 to 9.
        # First user in that range is at index 6.
        # So active should be history[6:], length 4, starting with "user".
        active, archived = manager.manage_history(history)
        self.assertEqual([t.role for t in active], ["user", "model", "user", "model"])
        self.assertEqual([t.role for t in archived], ["user", "model", "user", "model", "user", "model"])

    def test_long_history_no_user_in_preferred_range(self):
        manager = MemoryManager(max_history=3)
        history = [
            MockTurn("user"),  # 0
            MockTurn("model"), # 1
            MockTurn("tool"),  # 2
            MockTurn("model"), # 3
            MockTurn("tool"),  # 4
            MockTurn("model")  # 5
        ]
        # max_history = 3. Preferred range is from index 3 to 5.
        # Turns are: 3:model, 4:tool, 5:model. No user turn in range!
        # It should scan backwards and find user turn at index 0.
        # So active should be history[0:], keeping all elements because we must start with user.
        active, archived = manager.manage_history(history)
        self.assertEqual([t.role for t in active], ["user", "model", "tool", "model", "tool", "model"])
        self.assertEqual(archived, [])

    def test_no_user_turn_at_all(self):
        manager = MemoryManager(max_history=5)
        history = [
            MockTurn("model"),
            MockTurn("tool"),
            MockTurn("model")
        ]
        active, archived = manager.manage_history(history)
        # Should fallback to index 0
        self.assertEqual(active, history)
        self.assertEqual(archived, [])

    def test_dict_history(self):
        manager = MemoryManager(max_history=3)
        history = [
            {"role": "user"},
            {"role": "model"},
            {"role": "user"},
            {"role": "model"}
        ]
        active, archived = manager.manage_history(history)
        self.assertEqual(active, [{"role": "user"}, {"role": "model"}])
        self.assertEqual(archived, [{"role": "user"}, {"role": "model"}])

if __name__ == '__main__':
    unittest.main()

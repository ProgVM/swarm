import threading
import json
import time
import os
import unittest
from swarm.locking import SessionLockManager

class TestConcurrency(unittest.TestCase):
    def test_concurrent_updates(self):
        filename = 'test_session_concurrent.json'
        if os.path.exists(filename):
            os.remove(filename)
            
        with open(filename, 'w') as f:
            json.dump({'counter': 0}, f)

        def worker(fname):
            for _ in range(50):
                with SessionLockManager.atomic_update(fname) as data:
                    count = data.get('counter', 0)
                    data['counter'] = count + 1
                    time.sleep(0.001)

        threads = [threading.Thread(target=worker, args=(filename,)) for _ in range(10)]

        for t in threads: t.start()
        for t in threads: t.join()

        with open(filename, 'r') as f:
            final_data = json.load(f)
            
        self.assertEqual(final_data['counter'], 500)
        
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == '__main__':
    unittest.main()

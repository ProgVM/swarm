import threading
import json
import os
from contextlib import contextmanager

class SessionLockManager:
    _file_lock = threading.RLock()

    @staticmethod
    @contextmanager
    def atomic_update(file_path):
        with SessionLockManager._file_lock:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump({}, f)
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            yield data
            
            tmp_path = file_path + ".tmp"
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)

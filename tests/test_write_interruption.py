import os
import json
import shutil
import subprocess

def test_interruption():
    filepath = "test_session.json"
    try:
        with open(filepath, 'w') as f:
            json.dump({"old": "data"}, f)
        
        script = """
import os, json, shutil
filepath = 'test_session.json'
shutil.copy(filepath, filepath + '.bak')
tmp = filepath + '.tmp'
with open(tmp, 'w') as f:
    json.dump({'new': 'data'}, f)
os._exit(1)
"""
        with open("crash_script.py", "w") as f:
            f.write(script.strip())
        
        # Run script, expect crash (exit code 1), so check=False
        subprocess.run(["python3", "crash_script.py"], check=False)
        
        # Check
        assert os.path.exists(filepath)
        assert os.path.exists(filepath + ".bak")
        assert os.path.exists(filepath + ".tmp")
        
        with open(filepath) as f:
            assert json.load(f) == {"old": "data"}
            
        with open(filepath + ".bak") as f:
            assert json.load(f) == {"old": "data"}
            
        with open(filepath + ".tmp") as f:
            assert json.load(f) == {"new": "data"}
            
    finally:
        for f in [filepath, filepath + ".bak", filepath + ".tmp", "crash_script.py"]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

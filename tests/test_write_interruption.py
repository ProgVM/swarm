import os
import json
import shutil
import subprocess

def test_interruption():
    filepath = "test_session.json"
    with open(filepath, 'w') as f: json.dump({"old": "data"}, f)
    
    script = """
import os, json, shutil
filepath = 'test_session.json'
shutil.copy(filepath, filepath + '.bak')
tmp = filepath + '.tmp'
with open(tmp, 'w') as f:
    json.dump({'new': 'data'}, f)
os._exit(1)
    """
    with open("crash_script.py", "w") as f: f.write(script)
    subprocess.run(["python3", "crash_script.py"])
    
    # Проверка
    print(f"Original content: {open(filepath).read()}")
    print(f"Backup exists: {os.path.exists(filepath + '.bak')}")
    print(f"Backup content: {open(filepath + '.bak').read()}")

test_interruption()

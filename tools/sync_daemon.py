#!/usr/bin/env python3
"""
Background auto-sync watcher for Project Aid.
Checks for workspace changes every 2.5 minutes (150s) and runs auto_sync.sh.
"""

import time
import subprocess
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTO_SYNC_SH = os.path.join(SCRIPT_DIR, "auto_sync.sh")

print("Project Aid auto-sync daemon started. Checking every 150 seconds...")

while True:
    time.sleep(150)
    try:
        res = subprocess.run([AUTO_SYNC_SH], capture_output=True, text=True)
        if "Changes detected" in res.stdout:
            print(f"[AutoSync] {res.stdout.strip()}")
    except Exception as e:
        print(f"[AutoSync Error] {e}")

import schedule
import time
import subprocess
import os
import sys
from datetime import datetime


def wake_up_ghost():
    print(f"[{datetime.now()}] Ghost Committer is waking up for the night shift...")
    try:
        result = subprocess.run(
            [sys.executable, "main.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        print(f"[{datetime.now()}] Ghost Committer finished its shift.")
        print("--- Output ---")
        print(result.stdout)
        if result.stderr:
            print("--- Errors ---")
            print(result.stderr)
    except Exception as e:
        print(f"[{datetime.now()}] Failed to wake up Ghost: {e}")


def start_scheduler():
    print("--- Ghost Scheduler Started ---")
    print("Target: 02:00 AM every night.")
    schedule.every().day.at("02:00").do(wake_up_ghost)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("--- Ghost Scheduler: Test Mode ---")
        wake_up_ghost()
    else:
        start_scheduler()

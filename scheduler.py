import schedule
import time
import subprocess
import os
import sys
from datetime import datetime

def wake_up_ghost():
    print(f"[{datetime.now()}] 👻 Ghost Committer is waking up for the night shift...")
    try:
        # Run the main pipeline
        # We use sys.executable to ensure we use the same venv
        result = subprocess.run([sys.executable, "main.py", "."], capture_output=True, text=True)
        print(f"[{datetime.now()}] Ghost Committer finished its shift.")
        print("--- Output ---")
        print(result.stdout)
        if result.stderr:
            print("--- Errors ---")
            print(result.stderr)
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Failed to wake up Ghost: {e}")

def start_scheduler():
    print("--- 👻 Ghost Scheduler Started ---")
    print("Target: 02:00 AM every night.")
    
    # Schedule the job
    schedule.every().day.at("02:00").do(wake_up_ghost)
    
    # For testing: schedule one in 10 seconds if 'test' argument is passed
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("Test mode: Running Ghost in 5 seconds...")
        schedule.every(5).seconds.do(wake_up_ghost).tag('test-run')

    while True:
        schedule.run_pending()
        time.sleep(1)
        
        # If test run was done, cancel it so it doesn't loop
        if len(sys.argv) > 1 and sys.argv[1] == "test":
            schedule.clear('test-run')
            # Wait a bit for the subprocess to finish in test mode
            time.sleep(10) 

if __name__ == "__main__":
    start_scheduler()

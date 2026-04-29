import os
import argparse
from scanner.core import ScannerCore
from planner.agent import PlannerAgent

def run_ghost_committer(repo_path):
    print(f"--- Waking up Ghost Committer for {repo_path} ---")
    
    # Layer 2: Scanner
    scanner = ScannerCore(repo_path)
    report = scanner.generate_full_report()
    
    print("\n--- Scan Report ---")
    print(f"Lint issues: {len(report['findings'].get('lint', []))}")
    if report['findings'].get('dead_code'):
        print("Dead code detected.")
    else:
        print("No dead code detected.")
    
    # Layer 3: Planner
    planner = PlannerAgent()
    plan_result = planner.generate_plan(report)
    
    print("\n--- Proposed Plan ---")
    print(plan_result['plan'])
    
    # Next steps will connect to Patcher and Validator here
    print("\n--- Pipeline Paused (Patcher pending) ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost Committer - Autonomous Tech Debt Agent")
    parser.add_argument("path", nargs="?", default=".", help="Path to the repository to scan")
    args = parser.parse_args()
    
    # For testing, ensure it runs on the current directory
    target_path = os.path.abspath(args.path)
    run_ghost_committer(target_path)

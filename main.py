import os
import argparse
from scanner.core import ScannerCore
from planner.agent import PlannerAgent
from patcher.git_ops import GitPatcher
from validator.sandbox import SandboxValidator
from delivery.github_ops import GitHubDelivery
from delivery.slack_notify import SlackNotifier

def run_ghost_committer(repo_path):
    print(f"--- Waking up Ghost Committer for {repo_path} ---")
    
    # Layer 2: Scanner
    scanner = ScannerCore(repo_path)
    report = scanner.generate_full_report()
    
    lint_count = len(report['findings'].get('lint', []))
    print("\n--- Scan Report ---")
    print(f"Lint issues: {lint_count}")
    if report['findings'].get('dead_code'):
        print("Dead code detected.")
    else:
        print("No dead code detected.")
    
    # Layer 3: Planner
    planner = PlannerAgent()
    plan_result = planner.generate_plan(report)
    
    print("\n--- Proposed Plan ---")
    print(plan_result['plan'])
    
    # Layer 4: Patcher
    print("\n--- Patching ---")
    patcher = GitPatcher(repo_path)
    branch = None
    if patcher.repo:
        branch = patcher.create_branch("chore/ghost-auto")
        if branch:
            # Simulate the LLM applying a fix
            with open(os.path.join(repo_path, "dummy_fix.txt"), "a") as f:
                f.write("Fixed a simulated tech debt issue.\n")
            
            patcher.commit_changes("chore: apply overnight tech debt fixes")
            print(f"[Main] Changes committed to branch {branch}")
        else:
            print("[Main] Failed to create branch.")
    
    # Layer 5: Validator
    print("\n--- Validating ---")
    validator = SandboxValidator(repo_path)
    val_result = validator.run_tests()
    
    if val_result.get("status") == "success":
        print("\n--- Success: Pipeline Green ---")
        print("Ready for Delivery (PR creation).")
        
        # Layer 6: Delivery
        print("\n--- Delivery ---")
        github_del = GitHubDelivery()
        slack = SlackNotifier()
        
        # In a real environment, the GitPatcher would push to the remote here before opening the PR.
        
        if branch:
             pr_res = github_del.create_pull_request(
                  branch_name=branch, 
                  title="Chore: Overnight Tech Debt Cleanup", 
                  body=plan_result['plan']
             )
             
             if pr_res.get("status") in ["success", "dry_run"]:
                  slack.send_morning_digest(pr_url=pr_res.get("url"), stats={"lint_issues": lint_count})
                  
    else:
        print("\n--- Failed: Pipeline Red ---")
        print("Tests failed or sandbox error. PR will not be opened.")
        if "message" in val_result:
            print(f"Reason: {val_result['message']}")
        else:
             print(f"Output: {val_result.get('output')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost Committer - Autonomous Tech Debt Agent")
    parser.add_argument("path", nargs="?", default=".", help="Path to the repository to scan")
    args = parser.parse_args()
    
    # For testing, ensure it runs on the current directory
    target_path = os.path.abspath(args.path)
    run_ghost_committer(target_path)

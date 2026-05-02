import os
from dotenv import load_dotenv

load_dotenv()

import argparse  # noqa: E402
from scanner.core import ScannerCore  # noqa: E402
from planner.agent import PlannerAgent  # noqa: E402
from patcher.git_ops import GitPatcher  # noqa: E402
from validator.sandbox import SandboxValidator  # noqa: E402
from delivery.github_ops import GitHubDelivery  # noqa: E402
from delivery.slack_notify import SlackNotifier  # noqa: E402
from delivery.telegram_notify import TelegramNotifier  # noqa: E402

MAX_RETRIES = 3

def run_ghost_committer(repo_path):
    print(f"--- Waking up Ghost Committer for {repo_path} ---")

    # Layer 2: Scanner
    scanner = ScannerCore(repo_path)
    report = scanner.generate_full_report()

    lint_count = len(report["findings"].get("lint", []))
    todo_count = len(report.get("todos", []))
    complex_count = len(report.get("complex_functions", []))
    docstring_count = len(report.get("missing_docstrings", []))

    print("\n--- Scan Report ---")
    print(f"Lint issues: {lint_count}")
    if report["findings"].get("dead_code"):
        print("Dead code detected.")
    else:
        print("No dead code detected.")
    print(f"TODOs: {todo_count}")
    print(f"Complex functions: {complex_count}")
    print(f"Missing docstrings: {docstring_count}")

    # Layer 3: Planner
    planner = PlannerAgent()
    plan_result = planner.generate_plan(report)

    print("\n--- Proposed Plan ---")
    print(plan_result["plan"])

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

    # Layer 5: Validator with Self-Correction Loop
    print("\n--- Validating ---")
    validator = SandboxValidator(repo_path)
    val_result = validator.run_tests()

    retries_used = 0
    while val_result.get("status") != "success" and retries_used < MAX_RETRIES:
        retries_used += 1
        print(f"\n--- Validation Failed (Attempt {retries_used}/{MAX_RETRIES}) ---")
        failure_output = val_result.get("output", val_result.get("message", "Unknown error"))
        print(f"Failure reason: {failure_output}")

        # Append failure to report and re-plan
        report["previous_failure"] = failure_output
        print("[Main] Re-running planner with updated report...")
        plan_result = planner.generate_plan(report)
        print("\n--- Revised Plan ---")
        print(plan_result["plan"])

        # Re-apply patch (simulate another fix iteration)
        if branch and patcher.repo:
            with open(os.path.join(repo_path, "dummy_fix.txt"), "a") as f:
                f.write(f"Fixed a simulated tech debt issue (retry {retries_used}).\n")
            patcher.commit_changes(f"chore: apply overnight tech debt fixes (retry {retries_used})")
            patcher.push_branch(branch)
            print(f"[Main] Re-applied patch for retry {retries_used}")

        # Re-run validator
        print("\n--- Re-Validating ---")
        val_result = validator.run_tests()

    if val_result.get("status") == "success":
        print("\n--- Success: Pipeline Green ---")
        print("Ready for Delivery (PR creation).")

        # Layer 6: Delivery
        print("\n--- Delivery ---")
        github_del = GitHubDelivery()
        slack = SlackNotifier()
        telegram = TelegramNotifier()

        if branch:
            pr_res = github_del.create_pull_request(
                branch_name=branch,
                title="Chore: Overnight Tech Debt Cleanup",
                body=plan_result["plan"]
            )

            if pr_res.get("status") in ["success", "dry_run"]:
                stats = {
                    "lint_issues": lint_count,
                    "branch": branch,
                    "todos": todo_count,
                    "complex_functions": complex_count,
                    "missing_docstrings": docstring_count,
                }
                slack.send_morning_digest(pr_url=pr_res.get("url"), stats=stats)
                telegram.send_morning_digest(
                    pr_url=pr_res.get("url"),
                    stats=stats,
                    plan_summary=plan_result["plan"],
                    retries_used=retries_used,
                )
    else:
        print("\n--- Failed: Pipeline Red ---")
        print("Tests failed or sandbox error. PR will not be opened.")
        if "message" in val_result:
            print(f"Reason: {val_result['message']}")
        else:
            print(f"Output: {val_result.get('output')}")

        if branch and patcher.repo:
            patcher.cleanup_branch(branch)
            print("All retries exhausted. Branch deleted.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost Committer - Autonomous Tech Debt Agent")
    parser.add_argument("path", nargs="?", default=".", help="Path to the repository to scan")
    args = parser.parse_args()

    target_path = os.path.abspath(args.path)
    run_ghost_committer(target_path)

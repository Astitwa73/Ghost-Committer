import os
import argparse
import subprocess

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _oc_event(message: str):
    """Emit a system event to the OpenClaw gateway (best-effort, never fatal)."""
    try:
        subprocess.run(
            ["openclaw", "system", "event", "--message", message],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass

from scanner.core import ScannerCore
from planner.agent import PlannerAgent
from patcher.git_ops import GitPatcher
from validator.sandbox import SandboxValidator
from delivery.github_ops import GitHubDelivery
from delivery.slack_notify import SlackNotifier
from delivery.telegram_notify import TelegramNotifier

MAX_RETRIES = 3


def run_ghost_committer(repo_path):
    print(f"--- Waking up Ghost Committer for {repo_path} ---")
    _oc_event(f"ghost-committer: pipeline started for {repo_path}")

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

    _oc_event(
        f"ghost-committer: scan_complete — lint:{lint_count} todos:{todo_count} "
        f"complex:{complex_count} missing_docs:{docstring_count}"
    )

    # Layer 3: Planner
    planner = PlannerAgent()
    plan_result = planner.generate_plan(report)

    print("\n--- Proposed Plan ---")
    print(plan_result["plan"])

    _oc_event(f"ghost-committer: plan_complete — model:{plan_result.get('model','unknown')}")

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
            patcher.push_branch(branch)
            _oc_event(f"ghost-committer: patch_complete — branch:{branch}")
        else:
            print("[Main] Failed to create branch.")

    # Layer 5: Validator with Self-Correction Loop
    print("\n--- Validating ---")
    _oc_event("ghost-committer: validation_start")
    validator = SandboxValidator(repo_path)
    val_result = validator.run_tests()

    retries_used = 0
    last_failure = None
    while val_result.get("status") != "success" and retries_used < MAX_RETRIES:
        failure_output = val_result.get("output", val_result.get("message", "Unknown error"))

        # If the failure is identical to the last attempt, it's an infrastructure
        # issue that patching can't fix — stop retrying early.
        if failure_output == last_failure:
            print(f"\n--- Validation: Same failure repeated — stopping retries early ---")
            _oc_event("ghost-committer: validation_retry_aborted — repeated_failure")
            break
        last_failure = failure_output

        retries_used += 1
        _oc_event(f"ghost-committer: validation_retry attempt:{retries_used}/{MAX_RETRIES}")
        print(f"\n--- Validation Failed (Attempt {retries_used}/{MAX_RETRIES}) ---")
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
        detected_repo = patcher.get_github_repo_name()
        if detected_repo:
            print(f"[Main] Detected GitHub repo: {detected_repo}")
        github_del = GitHubDelivery(repo_name=detected_repo)
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
                _oc_event(
                    f"ghost-committer: delivery_complete — pr:{pr_res.get('url','dry-run')} "
                    f"retries:{retries_used}"
                )
    else:
        print("\n--- Failed: Pipeline Red ---")
        _oc_event(f"ghost-committer: pipeline_failed — retries_exhausted:{retries_used}")
        print("Tests failed or sandbox error. PR will not be opened.")
        if "message" in val_result:
            print(f"Reason: {val_result['message']}")
        else:
            print(f"Output: {val_result.get('output')}")

        print(f"All {MAX_RETRIES} retries exhausted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost Committer - Autonomous Tech Debt Agent")
    parser.add_argument("path", nargs="?", default=".", help="Path to the repository to scan")
    args = parser.parse_args()

    target_path = os.path.abspath(args.path)
    run_ghost_committer(target_path)

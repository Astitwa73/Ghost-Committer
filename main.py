import os
import argparse
import requests
import datetime
import shutil
import tempfile

# Monkeypatch cmdop.exceptions before importing openclaw
import cmdop.exceptions
if not hasattr(cmdop.exceptions, "TimeoutError"):
    cmdop.exceptions.TimeoutError = cmdop.exceptions.ConnectionTimeoutError

from openclaw import OpenClaw

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def send_openclaw_heartbeat(status: str, message: str):
    """Sends a heartbeat to the OpenClaw platform using the SDK."""
    api_key = os.getenv("OPENCLAW_API_KEY")
    server_url = os.getenv("OPENCLAW_SERVER_URL")

    if api_key:
        try:
            print(f"[OpenClaw] Connecting via SDK to send status: {status}")
            client = OpenClaw.remote(api_key=api_key, server=server_url or "grpc.cmdop.com:443")
            client.agent.run(f"Status Update: {status} - {message}", session_id="ghost-committer-session")
            client.close()
            return
        except Exception as e:
            print(f"[OpenClaw] SDK Heartbeat failed: {e}")

    heartbeat_url = os.getenv("OPENCLAW_HEARTBEAT_URL")
    if heartbeat_url:
        try:
            print(f"[OpenClaw] Sending REST heartbeat: {status} - {message}")
            requests.post(
                heartbeat_url,
                json={"agent": "ghost-committer", "status": status, "message": message},
                timeout=5
            )
        except Exception as e:
            print(f"[OpenClaw] REST Heartbeat failed: {e}")
    else:
        print(f"[OpenClaw] Warning: OpenClaw credentials/URL not set. Skipping heartbeat: {status}")


def _clone_target_repo():
    """Clone GITHUB_REPOSITORY to a temp dir using GITHUB_TOKEN. Returns (path, tmpdir)."""
    github_repo = os.environ.get("GITHUB_REPOSITORY")
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_repo:
        return None, None
    tmpdir = tempfile.mkdtemp(prefix="ghost-committer-target-")
    auth_url = f"https://{github_token}@github.com/{github_repo}.git" if github_token else f"https://github.com/{github_repo}.git"
    print(f"[Main] Cloning target repo: {github_repo}")
    try:
        import subprocess as _sp
        _sp.run(["git", "clone", auth_url, tmpdir], check=True, capture_output=True)
        print(f"[Main] Cloned to: {tmpdir}")
        return tmpdir, tmpdir
    except Exception as e:
        print(f"[Main] Failed to clone {github_repo}: {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, None


from scanner.core import ScannerCore
from planner.agent import PlannerAgent
from patcher.git_ops import GitPatcher
from validator.sandbox import SandboxValidator
from delivery.github_ops import GitHubDelivery
from delivery.slack_notify import SlackNotifier
from delivery.telegram_notify import TelegramNotifier

MAX_RETRIES = 3


def run_ghost_committer(repo_path, tmpdir_to_cleanup=None):
    print(f"--- Waking up Ghost Committer for {repo_path} ---")
    send_openclaw_heartbeat("starting", f"Ghost Committer waking up for {repo_path}")

    try:
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

        # Layer 4: Patcher — works entirely inside the cloned target repo
        print("\n--- Patching ---")
        patcher = GitPatcher(repo_path)
        branch = None
        files_fixed = []

        if patcher.repo:
            branch = patcher.create_branch("chore/ghost-auto")
            if branch:
                # 1. Fix ALL missing docstrings
                if report.get("missing_docstrings"):
                    print(f"[Main] Found {len(report['missing_docstrings'])} docstring issues. Patching...")
                    for issue in report["missing_docstrings"]:
                        filename = issue.get("file") or issue.get("filename")
                        file_path = os.path.join(repo_path, filename)
                        if os.path.exists(file_path):
                            with open(file_path, "r") as f:
                                original_content = f.read()
                            description = f"Add missing docstring to function '{issue.get('name', 'unknown')}' at line {issue['line']}."
                            updated_content = planner.generate_patch(original_content, description)
                            if updated_content and updated_content != original_content:
                                with open(file_path, "w") as f:
                                    f.write(updated_content)
                                print(f"[Main] Applied autonomous fix: {description}")
                                if file_path not in files_fixed:
                                    files_fixed.append(file_path)

                # 2. Resolve ALL TODOs
                if report.get("todos"):
                    print(f"[Main] Found {len(report['todos'])} TODOs. Patching...")
                    for issue in report["todos"]:
                        filename = issue.get("file") or issue.get("filename")
                        file_path = os.path.join(repo_path, filename)
                        if os.path.exists(file_path):
                            with open(file_path, "r") as f:
                                original_content = f.read()
                            description = f"Resolve TODO at line {issue['line']}: {issue.get('content', issue.get('text', ''))}"
                            updated_content = planner.generate_patch(original_content, description)
                            if updated_content and updated_content != original_content:
                                with open(file_path, "w") as f:
                                    f.write(updated_content)
                                print(f"[Main] Applied autonomous fix: {description}")
                                if file_path not in files_fixed:
                                    files_fixed.append(file_path)

                # 3. Simplify ALL Complex Functions
                if report.get("complex_functions"):
                    print(f"[Main] Found {len(report['complex_functions'])} complex functions. Patching...")
                    for func in report["complex_functions"]:
                        filename = func.get("file") or func.get("filename")
                        file_path = os.path.join(repo_path, filename)
                        if os.path.exists(file_path):
                            with open(file_path, "r") as f:
                                original_content = f.read()
                            description = f"Simplify the function '{func.get('name', 'unknown')}' (currently too complex with high nesting)."
                            updated_content = planner.generate_patch(original_content, description)
                            if updated_content and updated_content != original_content:
                                with open(file_path, "w") as f:
                                    f.write(updated_content)
                                print(f"[Main] Applied autonomous fix: {description}")
                                if file_path not in files_fixed:
                                    files_fixed.append(file_path)

                if not files_fixed:
                    print("[Main] No autonomous fixes applied. Falling back to log.")
                    with open(os.path.join(repo_path, "PATCH_LOG.md"), "a") as f:
                        f.write(f"[{datetime.datetime.now()}] Ran pipeline, no auto-patches applied.\n")
                else:
                    print(f"[Main] Successfully patched {len(files_fixed)} unique files.")

                patcher.commit_changes("chore: apply autonomous overnight tech debt fixes")
                print(f"[Main] Changes committed to branch {branch}")
                patcher.push_branch(branch)
            else:
                print("[Main] Failed to create branch.")

        # Layer 5: Validator with Self-Correction Loop
        print("\n--- Validating ---")
        validator = SandboxValidator(repo_path)
        val_result = validator.run_tests()

        retries_used = 0
        last_failure = None
        last_fixed_file = files_fixed[0] if files_fixed else None

        while val_result.get("status") != "success" and retries_used < MAX_RETRIES:
            failure_output = val_result.get("output", val_result.get("message", "Unknown error"))

            # Early-exit: same failure repeating means it's infrastructure, not fixable code
            if failure_output == last_failure:
                print("\n--- Validation: Same failure repeated — stopping retries early ---")
                send_openclaw_heartbeat("warning", "Repeated validation failure — aborting retries")
                break
            last_failure = failure_output

            retries_used += 1
            print(f"\n--- Validation Failed (Attempt {retries_used}/{MAX_RETRIES}) ---")
            print(f"Failure reason: {failure_output}")

            if not last_fixed_file:
                import re
                matches = re.findall(r"([a-zA-Z0-9_\-]+\.py)", failure_output)
                if matches:
                    source_matches = [m for m in matches if "test_" not in m]
                    target = source_matches[0] if source_matches else matches[0]
                    last_fixed_file = os.path.join(repo_path, target)

            if last_fixed_file and os.path.exists(last_fixed_file):
                print(f"[Main] Self-Correction: Asking Planner to fix the failure in {os.path.basename(last_fixed_file)}...")
                with open(last_fixed_file, "r") as f:
                    current_content = f.read()
                correction_desc = f"The code is failing tests with this error: {failure_output}. Please fix the code to resolve this error."
                corrected_content = planner.generate_patch(current_content, correction_desc)
                if corrected_content and corrected_content != current_content:
                    with open(last_fixed_file, "w") as f:
                        f.write(corrected_content)
                    print(f"[Main] Applied self-correction patch to {os.path.basename(last_fixed_file)}")
                    if branch and patcher.repo:
                        patcher.commit_changes(f"chore: self-correction for validation failure (retry {retries_used})")
                        patcher.push_branch(branch)
                else:
                    print("[Main] Planner could not generate a better fix.")
            else:
                print("[Main] No file to self-correct or file missing.")

            print("\n--- Re-Validating ---")
            val_result = validator.run_tests()

        if val_result.get("status") == "success":
            print("\n--- Success: Pipeline Green ---")
            send_openclaw_heartbeat("success", "Pipeline Green. Delivering PR.")
            print("Ready for Delivery (PR creation).")

            # Layer 6: Delivery — detect repo from the target repo's own git remote
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
        else:
            print("\n--- Failed: Pipeline Red ---")
            send_openclaw_heartbeat("failed", "Pipeline Red. Tests failed.")
            print("Tests failed or sandbox error. PR will not be opened.")
            if "message" in val_result:
                print(f"Reason: {val_result['message']}")
            else:
                print(f"Output: {val_result.get('output')}")
            print(f"All {MAX_RETRIES} retries exhausted.")

    finally:
        if tmpdir_to_cleanup:
            print(f"[Main] Cleaning up cloned repo at {tmpdir_to_cleanup}")
            shutil.rmtree(tmpdir_to_cleanup, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ghost Committer - Autonomous Tech Debt Agent")
    parser.add_argument("path", nargs="?", default=None, help="Path to the repository to scan (defaults to GITHUB_REPOSITORY clone)")
    args = parser.parse_args()

    if args.path:
        run_ghost_committer(os.path.abspath(args.path))
    else:
        cloned_path, tmpdir = _clone_target_repo()
        if cloned_path:
            run_ghost_committer(cloned_path, tmpdir_to_cleanup=tmpdir)
        else:
            print("[Main] No path given and GITHUB_REPOSITORY not set or clone failed. Aborting.")

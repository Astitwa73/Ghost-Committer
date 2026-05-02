import json
import os

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

class PlannerAgent:
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.client = None
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

        if Anthropic and self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                print("[Planner] Anthropic client initialized.")
            except Exception as e:
                print(f"[Planner] Failed to initialize Anthropic client: {e}. Falling back to mock mode.")
        else:
            if not self.api_key:
                print("[Planner] ANTHROPIC_API_KEY not found. Running in mock mode.")
            elif not Anthropic:
                print("[Planner] anthropic SDK not installed. Running in mock mode.")

    def generate_plan(self, scan_report):
        """Analyzes scan report and plans fixes."""
        print("[Planner] Analyzing scan report...")

        lint_issues = scan_report.get("findings", {}).get("lint", [])
        dead_code = scan_report.get("findings", {}).get("dead_code", "")
        vulnerabilities = scan_report.get("findings", {}).get("vulnerabilities", [])
        todos = scan_report.get("todos", [])
        complex_functions = scan_report.get("complex_functions", [])
        missing_docstrings = scan_report.get("missing_docstrings", [])
        previous_failure = scan_report.get("previous_failure")

        has_issues = any([
            lint_issues, dead_code, vulnerabilities,
            todos, complex_functions, missing_docstrings, previous_failure
        ])

        if not has_issues:
            return {"status": "success", "plan": "No issues found. Code is clean.", "source": "mock"}

        if self.client:
            return self._call_claude(scan_report)
        else:
            mock_plan = self._build_mock_plan(
                lint_issues, dead_code, vulnerabilities,
                todos, complex_functions, missing_docstrings, previous_failure
            )
            return {"status": "mock", "plan": mock_plan, "source": "mock"}

    def _call_claude(self, scan_report):
        system_prompt = (
            "You are a senior software engineer specializing in code quality. "
            "You will be given a JSON scan report of a Python codebase. Your job is to "
            "produce a concise, actionable fix plan. Apply three rules:\n"
            "Rule 1: Identify TODO comments that should be resolved and suggest fixes.\n"
            "Rule 2: Flag functions with deep nesting (3+ levels of if/else) and suggest "
            "how to simplify them.\n"
            "Rule 3: List any exported functions missing docstrings.\n"
            "Format your output as a numbered plan. Be specific and brief."
        )
        user_message = f"Here is the scan report:\n{json.dumps(scan_report, indent=2)}"

        try:
            print("[Planner] Querying Claude for fix plan...")
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            plan_text = response.content[0].text.strip()
            return {"status": "success", "plan": plan_text, "source": "claude"}
        except Exception as e:
            print(f"[Planner] Claude API call failed: {e}. Falling back to mock plan.")
            lint_issues = scan_report.get("findings", {}).get("lint", [])
            dead_code = scan_report.get("findings", {}).get("dead_code", "")
            vulnerabilities = scan_report.get("findings", {}).get("vulnerabilities", [])
            todos = scan_report.get("todos", [])
            complex_functions = scan_report.get("complex_functions", [])
            missing_docstrings = scan_report.get("missing_docstrings", [])
            previous_failure = scan_report.get("previous_failure")
            mock_plan = self._build_mock_plan(
                lint_issues, dead_code, vulnerabilities,
                todos, complex_functions, missing_docstrings, previous_failure
            )
            return {"status": "mock", "plan": mock_plan, "source": "mock"}

    def _build_mock_plan(self, lint, dead, vulns, todos, complex_functions, missing_docstrings, previous_failure):
        plan_lines = ["MOCK PLAN:"]
        if lint:
            plan_lines.append(f"1. Fix {len(lint)} lint issues.")
        if dead:
            plan_lines.append("2. Remove dead code.")
        if vulns:
            plan_lines.append("3. Update dependencies to patch vulnerabilities.")
        if todos:
            plan_lines.append(f"4. Resolve {len(todos)} TODO/FIXME comments.")
        if complex_functions:
            plan_lines.append(f"5. Simplify {len(complex_functions)} deeply nested functions.")
        if missing_docstrings:
            plan_lines.append(f"6. Add docstrings to {len(missing_docstrings)} functions.")
        if previous_failure:
            plan_lines.append("7. Address previous test failure before re-applying fixes.")
        return "\n".join(plan_lines)

if __name__ == "__main__":
    planner = PlannerAgent()
    dummy_report = {
        "findings": {
            "lint": [{"message": "Unused import sys", "filename": "main.py", "location": {"row": 1}}],
            "dead_code": "main.py:10: unused function 'old_helper'",
            "vulnerabilities": []
        },
        "todos": [],
        "complex_functions": [],
        "missing_docstrings": []
    }
    print(json.dumps(planner.generate_plan(dummy_report), indent=2))

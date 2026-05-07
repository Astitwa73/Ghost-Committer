import json
import os
import time
import logging

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI, RateLimitError, APIError
except ImportError:
    OpenAI = None
    RateLimitError = Exception
    APIError = Exception

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

_PLANNER_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PLANNER_DIR)
_DEFAULT_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "Phi-3-mini-4k-instruct-q4.gguf")


class PlannerAgent:
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 1.0
    MAX_BACKOFF = 60.0
    BACKOFF_MULTIPLIER = 2.0

    def __init__(self, model_path=None):
        """Initialize the PlannerAgent with model path and API configuration."""
        self.model_path = model_path or _DEFAULT_MODEL_PATH
        self.llm = None
        self.client = None
        self.model_id = os.environ.get("OPENCODE_MODEL", "kimi-k2.6")
        self.api_key = os.environ.get("OPENCODE_API_KEY")
        self.base_url = os.environ.get("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1")

        if OpenAI and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=60.0)
                print(f"[Planner] OpenAI-compatible client initialized (model={self.model_id}).")
            except Exception as e:
                print(f"[Planner] Failed to initialize OpenAI client: {e}")
                self.client = None

        if not self.client and Llama and os.path.exists(self.model_path):
            print(f"[Planner] Loading local model from {self.model_path}...")
            self.llm = Llama(model_path=self.model_path, n_ctx=4096, verbose=False)
        elif not self.client:
            if not self.api_key:
                print("[Planner] OPENCODE_API_KEY not found.")
            print("[Planner] Running in mock mode.")

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

        # Treat pip-audit error dicts as "no real vulnerabilities"
        real_vulns = vulnerabilities if isinstance(vulnerabilities, list) and vulnerabilities else []

        has_issues = any([
            lint_issues, dead_code, real_vulns,
            todos, complex_functions, missing_docstrings, previous_failure
        ])

        if not has_issues:
            return {"status": "success", "plan": "No issues found. Code is clean.", "source": "none"}

        if self.client:
            return self._call_api_with_retry(scan_report)

        if self.llm:
            return self._call_local_llm(scan_report)

        return self._generate_mock_plan(scan_report)

    def _call_api_with_retry(self, scan_report):
        """Call OpenAI-compatible API with exponential backoff."""
        backoff = self.INITIAL_BACKOFF

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call_api(scan_report)
            except RateLimitError as e:
                if attempt == self.MAX_RETRIES - 1:
                    print(f"[Planner] Rate limit exceeded after {self.MAX_RETRIES} retries. Falling back to mock.")
                    logger.warning(f"API rate limit exceeded: {e}")
                    return self._generate_mock_plan(scan_report)

                wait_time = min(backoff, self.MAX_BACKOFF)
                print(f"[Planner] Rate limited. Waiting {wait_time:.1f}s before retry {attempt + 2}/{self.MAX_RETRIES}...")
                time.sleep(wait_time)
                backoff *= self.BACKOFF_MULTIPLIER
            except APIError as e:
                print(f"[Planner] API error: {e}. Falling back to mock.")
                logger.error(f"API error: {e}")
                return self._generate_mock_plan(scan_report)
            except Exception as e:
                print(f"[Planner] Unexpected error: {e}. Falling back to mock.")
                logger.error(f"Unexpected error calling API: {e}")
                return self._generate_mock_plan(scan_report)

        return self._generate_mock_plan(scan_report)

    def _call_api(self, scan_report):
        """Make a single API call."""
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

        truncated_report = self._truncate_report(scan_report)
        user_message = f"Here is the scan report:\n{json.dumps(truncated_report, indent=2)}"

        print(f"[Planner] Querying {self.model_id} for fix plan...")
        response = self.client.chat.completions.create(
            model=self.model_id,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            print("[Planner] API returned empty content. Falling back to mock.")
            return self._generate_mock_plan(scan_report)
        plan_text = content.strip()
        return {"status": "success", "plan": plan_text, "source": self.model_id}

    def _truncate_report(self, scan_report):
        """Truncate report to reduce token usage."""
        truncated = {
            "findings": {},
            "timestamp": scan_report.get("timestamp", ""),
        }

        findings = scan_report.get("findings", {})

        lint = findings.get("lint", [])
        if lint:
            truncated["findings"]["lint"] = lint[:10]
            if len(lint) > 10:
                truncated["findings"]["lint_total"] = len(lint)

        dead_code = findings.get("dead_code", "")
        if dead_code:
            truncated["findings"]["dead_code"] = dead_code[:500]

        vulns = findings.get("vulnerabilities", [])
        if isinstance(vulns, list) and vulns:
            truncated["findings"]["vulnerabilities"] = vulns[:5]
            if len(vulns) > 5:
                truncated["findings"]["vulnerabilities_total"] = len(vulns)
        elif isinstance(vulns, dict) and "error" not in vulns and vulns:
            truncated["findings"]["vulnerabilities"] = vulns

        if scan_report.get("todos"):
            truncated["todos"] = scan_report["todos"][:5]
        if scan_report.get("complex_functions"):
            truncated["complex_functions"] = scan_report["complex_functions"][:5]
        if scan_report.get("missing_docstrings"):
            truncated["missing_docstrings"] = scan_report["missing_docstrings"][:5]
        if scan_report.get("previous_failure"):
            truncated["previous_failure"] = str(scan_report["previous_failure"])[:300]

        return truncated

    def _call_local_llm(self, scan_report):
        """Call local LLM via llama-cpp."""
        print("[Planner] Querying local LLM for fix plan...")
        prompt = self._build_prompt(scan_report)

        response = self.llm(
            prompt,
            max_tokens=512,
            stop=["<|end|>", "<|user|>", "<|system|>", "---"],
            echo=False
        )
        raw_text = response['choices'][0]['text'].strip()
        return {"status": "success", "plan": raw_text, "source": "llama"}

    def _build_prompt(self, scan_report):
        """Build prompt for local LLM."""
        findings = scan_report.get("findings", {})
        lint = findings.get("lint", [])
        dead = findings.get("dead_code", "")
        vulns = findings.get("vulnerabilities", [])
        todos = scan_report.get("todos", [])
        complex_funcs = scan_report.get("complex_functions", [])
        missing_docs = scan_report.get("missing_docstrings", [])

        prompt = "<|user|>\nYou are Ghost Committer, an autonomous AI developer agent. Create a concise, actionable plan to fix the following issues:\n\n"
        if lint and isinstance(lint, list):
            prompt += f"Linting Issues:\n{json.dumps(lint[:5], indent=2)}\n"
        if dead:
            prompt += f"Dead Code:\n{dead[:500]}\n"
        if isinstance(vulns, list) and vulns:
            prompt += f"Vulnerabilities:\n{json.dumps(vulns[:5], indent=2)}\n"

        if todos and isinstance(todos, list):
            prompt += f"TODO Comments:\n{json.dumps(todos[:5], indent=2)}\n"
        if complex_funcs and isinstance(complex_funcs, list):
            prompt += f"Complex Functions:\n{json.dumps(complex_funcs[:5], indent=2)}\n"
        if missing_docs and isinstance(missing_docs, list):
            prompt += f"Missing Docstrings:\n{json.dumps(missing_docs[:5], indent=2)}\n"

        prompt += "\n<|end|>\n<|assistant|>\n1."
        return prompt

    def _generate_mock_plan(self, scan_report):
        """Generate a mock plan when APIs are unavailable."""
        todos = scan_report.get("todos", [])
        complex_funcs = scan_report.get("complex_functions", [])
        missing_docs = scan_report.get("missing_docstrings", [])
        lint_issues = scan_report.get("findings", {}).get("lint", [])

        steps = []
        step_num = 1

        if lint_issues:
            steps.append(f"{step_num}. Fix {len(lint_issues)} linting issue(s) identified by ruff (unused imports, style violations).")
            step_num += 1

        if todos:
            for t in todos[:3]:
                steps.append(f"{step_num}. Resolve TODO at {t.get('file', '?')}:{t.get('line', '?')} — {t.get('content', '')[:80]}")
                step_num += 1

        if complex_funcs:
            for f in complex_funcs[:3]:
                steps.append(f"{step_num}. Simplify function '{f.get('name', '?')}' in {f.get('file', '?')} (high cyclomatic complexity).")
                step_num += 1

        if missing_docs:
            for d in missing_docs[:3]:
                steps.append(f"{step_num}. Add docstring to function '{d.get('name', '?')}' in {d.get('file', '?')}:{d.get('line', '?')}.")
                step_num += 1

        if not steps:
            steps.append("1. No actionable issues found — codebase is clean.")

        plan_text = "\n".join(steps)
        return {"status": "success", "plan": plan_text, "source": "mock"}

    def generate_patch(self, file_content, issue_description):
        """Generates a patch for a specific file and issue."""
        truncated_issue = issue_description[:2000] if len(issue_description) > 2000 else issue_description
        print(f"[Planner] Generating patch for issue: {truncated_issue[:50]}...")

        raw_patch = ""

        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    max_tokens=4096,
                    messages=[
                        {"role": "system", "content": "Output only raw Python file content. No markdown, no explanations, no code blocks."},
                        {"role": "user", "content": (
                            f"--- ORIGINAL FILE CONTENT ---\n{file_content}\n\n"
                            f"--- ISSUE TO FIX ---\n{truncated_issue}\n\n"
                            "Provide the complete updated Python file content now."
                        )},
                    ],
                )
                content = response.choices[0].message.content
                if content:
                    raw_patch = content.strip()
            except Exception as e:
                print(f"[Planner] Patch API call failed: {e}")

        elif self.llm:
            # Phi-3 has 4096 token context; truncate large files to ~2000 chars
            # so there's room for prompt overhead and the generated output
            safe_content = file_content[:2000] if len(file_content) > 2000 else file_content
            prompt = (
                "<|user|>\n"
                "No markdown, no explanations.\n\n"
                f"--- ORIGINAL FILE CONTENT ---\n{safe_content}\n\n"
                f"--- ISSUE TO FIX ---\n{truncated_issue}\n\n"
                "Provide the complete updated Python file content now.\n"
                "<|end|>\n<|assistant|>\n"
            )
            try:
                response = self.llm(
                    prompt,
                    max_tokens=2048,
                    stop=["<|end|>", "<|user|>", "<|system|>", "---"],
                    echo=False
                )
                raw_patch = response['choices'][0]['text'].strip()
            except Exception as e:
                print(f"[Planner] Local LLM patch error: {e}")
                return file_content

        if not raw_patch:
            return file_content

        lines = raw_patch.splitlines()
        clean_lines = []

        for line in lines:
            trimmed = line.strip().lower()
            if not clean_lines and not trimmed:
                continue
            if any(phrase in trimmed for phrase in stop_phrases) and len(trimmed) < 100:
                continue
            clean_lines.append(line)

        final_code = "\n".join(clean_lines).strip()

        if len(final_code) < 10:
            print("[Planner] Warning: LLM returned empty or invalid patch. Falling back.")
            return file_content

        return final_code


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
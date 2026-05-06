import json
import os
import time
import logging

logger = logging.getLogger(__name__)

# Absolute path to the project root (one level above this file's directory)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "Phi-3-mini-4k-instruct-q4.gguf")

try:
    from openai import OpenAI, APIError, RateLimitError, APIConnectionError
except ImportError:
    OpenAI = None
    APIError = Exception
    RateLimitError = Exception
    APIConnectionError = Exception

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


class PlannerAgent:
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 1.0
    MAX_BACKOFF = 60.0
    BACKOFF_MULTIPLIER = 2.0

    SYSTEM_PROMPT = (
        "You are a senior software engineer specializing in code quality. "
        "You will be given a JSON scan report of a Python codebase. Your job is to "
        "produce a concise, actionable fix plan. Apply three rules:\n"
        "Rule 1: Identify TODO comments that should be resolved and suggest fixes.\n"
        "Rule 2: Flag functions with deep nesting (3+ levels of if/else) and suggest "
        "how to simplify them.\n"
        "Rule 3: List any exported functions missing docstrings.\n"
        "Format your output as a numbered plan. Be specific and brief."
    )

    # Phi-3 instruct stop tokens
    _LOCAL_STOP_TOKENS = ["<|end|>", "<|endoftext|>", "<|user|>"]

    def __init__(self, model_path=None):
        self.model_path = model_path or _DEFAULT_MODEL_PATH
        self.llm = None
        self.client = None

        self.api_key = os.environ.get("OPENCODE_API_KEY")
        self.model_name = os.environ.get("OPENCODE_MODEL", "opencode-go/kimi-k2.6")
        self.base_url = os.environ.get("OPENCODE_BASE_URL")  # optional override

        if OpenAI and self.api_key:
            try:
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self.client = OpenAI(**kwargs)
                print(f"[Planner] OpenAI-compatible client initialized (model: {self.model_name}).")
            except Exception as e:
                print(f"[Planner] Failed to initialize API client: {e}")
                self.client = None

        if not self.client and Llama and os.path.exists(self.model_path):
            print(f"[Planner] Loading local model from {self.model_path}...")
            self.llm = Llama(model_path=self.model_path, n_ctx=4096, verbose=False)
        elif not self.client:
            if not self.api_key:
                print("[Planner] OPENCODE_API_KEY not found.")
            if not (Llama and os.path.exists(self.model_path)):
                print(f"[Planner] Local model not found at {self.model_path}.")
            print("[Planner] Running in mock mode.")

    def generate_plan(self, scan_report):
        print("[Planner] Analyzing scan report...")

        findings = scan_report.get("findings", {})
        has_issues = any([
            findings.get("lint"),
            findings.get("dead_code"),
            findings.get("vulnerabilities"),
            scan_report.get("todos"),
            scan_report.get("complex_functions"),
            scan_report.get("missing_docstrings"),
            scan_report.get("previous_failure"),
        ])

        if not has_issues:
            return {"status": "success", "plan": "No issues found. Code is clean.", "source": "none"}

        if self.client:
            return self._call_api_with_retry(scan_report)

        if self.llm:
            return self._call_local_llm(scan_report)

        return self._generate_mock_plan(scan_report)

    def _call_api_with_retry(self, scan_report):
        backoff = self.INITIAL_BACKOFF

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call_api(scan_report)
            except RateLimitError as e:
                if attempt == self.MAX_RETRIES - 1:
                    print(f"[Planner] Rate limit exceeded after {self.MAX_RETRIES} retries. Falling back to mock.")
                    logger.warning(f"Rate limit: {e}")
                    return self._generate_mock_plan(scan_report)
                wait_time = min(backoff, self.MAX_BACKOFF)
                print(f"[Planner] Rate limited. Waiting {wait_time:.1f}s before retry {attempt + 2}/{self.MAX_RETRIES}...")
                time.sleep(wait_time)
                backoff *= self.BACKOFF_MULTIPLIER
            except (APIError, APIConnectionError) as e:
                print(f"[Planner] API error: {e}. Falling back to mock.")
                logger.error(f"API error: {e}")
                return self._generate_mock_plan(scan_report)
            except Exception as e:
                print(f"[Planner] Unexpected error: {e}. Falling back to mock.")
                logger.error(f"Unexpected error calling API: {e}")
                return self._generate_mock_plan(scan_report)

        return self._generate_mock_plan(scan_report)

    def _call_api(self, scan_report):
        truncated = self._truncate_report(scan_report)
        user_content = f"Here is the scan report:\n{json.dumps(truncated, indent=2)}"

        print(f"[Planner] Querying {self.model_name} for fix plan...")
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=4096,
        )
        content = response.choices[0].message.content
        if not content:
            # reasoning-only response (all tokens consumed by thinking); fall back
            return self._generate_mock_plan(scan_report)
        return {"status": "success", "plan": content.strip(), "source": self.model_name}

    def _truncate_report(self, scan_report):
        truncated = {
            "findings": {},
            "timestamp": scan_report.get("timestamp", ""),
        }

        findings = scan_report.get("findings", {})

        lint = findings.get("lint", [])
        if isinstance(lint, list) and lint:
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
        print("[Planner] Querying local LLM (Phi-3) for fix plan...")
        prompt = self._build_prompt(scan_report)
        response = self.llm(
            prompt,
            max_tokens=512,
            stop=self._LOCAL_STOP_TOKENS,
            echo=False,
        )
        raw_text = response['choices'][0]['text'].strip()
        return {"status": "success", "plan": raw_text, "source": "phi-3-local"}

    def _build_prompt(self, scan_report):
        findings = scan_report.get("findings", {})
        lint = findings.get("lint", [])
        dead = findings.get("dead_code", "")
        vulns = findings.get("vulnerabilities", [])
        todos = scan_report.get("todos", [])
        complex_fns = scan_report.get("complex_functions", [])
        missing_docs = scan_report.get("missing_docstrings", [])
        prev_failure = scan_report.get("previous_failure", "")

        user_content = (
            "You are Ghost Committer, an autonomous code quality agent. "
            "Produce a concise numbered plan to fix the issues below.\n\n"
        )
        if lint:
            user_content += f"Lint issues ({len(lint)} total):\n{json.dumps(lint[:5], indent=2)}\n\n"
        if dead:
            user_content += f"Dead code:\n{dead[:400]}\n\n"
        if vulns:
            user_content += f"Vulnerable dependencies ({len(vulns)} total):\n{json.dumps(vulns[:5], indent=2)}\n\n"
        if todos:
            user_content += f"TODO/FIXME comments ({len(todos)} total):\n{json.dumps(todos[:5], indent=2)}\n\n"
        if complex_fns:
            user_content += f"Overly complex functions ({len(complex_fns)} total):\n{json.dumps(complex_fns[:5], indent=2)}\n\n"
        if missing_docs:
            user_content += f"Functions missing docstrings ({len(missing_docs)} total):\n{json.dumps(missing_docs[:5], indent=2)}\n\n"
        if prev_failure:
            user_content += f"Previous test failure to address:\n{str(prev_failure)[:300]}\n\n"

        user_content += "Numbered fix plan:\n1."

        # Phi-3 instruct chat template
        return f"<|user|>\n{user_content}<|end|>\n<|assistant|>\n1."

    def _generate_mock_plan(self, scan_report):
        findings = scan_report.get("findings", {})
        lint = findings.get("lint", [])
        dead = findings.get("dead_code", "")
        vulns = findings.get("vulnerabilities", [])

        plan_lines = ["MOCK PLAN:"]
        step = 1

        if lint:
            plan_lines.append(f"{step}. Fix {len(lint)} lint issues.")
            step += 1
        if dead:
            plan_lines.append(f"{step}. Remove dead code.")
            step += 1
        if vulns:
            plan_lines.append(f"{step}. Update dependencies to patch {len(vulns)} vulnerabilities.")
            step += 1
        if scan_report.get("todos"):
            plan_lines.append(f"{step}. Resolve {len(scan_report['todos'])} TODO/FIXME comments.")
            step += 1
        if scan_report.get("complex_functions"):
            plan_lines.append(f"{step}. Simplify {len(scan_report['complex_functions'])} deeply nested functions.")
            step += 1
        if scan_report.get("missing_docstrings"):
            plan_lines.append(f"{step}. Add docstrings to {len(scan_report['missing_docstrings'])} functions.")
            step += 1
        if scan_report.get("previous_failure"):
            plan_lines.append(f"{step}. Address previous test failure before re-applying fixes.")

        return {"status": "mock", "plan": "\n".join(plan_lines), "source": "mock"}


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

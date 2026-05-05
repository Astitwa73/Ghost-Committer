import json
import os
import time
import logging

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types as genai_types
    from google.genai.errors import ClientError as GeminiClientError
except ImportError:
    genai = None
    genai_types = None
    GeminiClientError = Exception

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

    def __init__(self, model_path="models/phi-3-mini-4k-instruct.Q4_K_M.gguf"):
        self.model_path = model_path
        self.llm = None
        self.model = None
        self.api_key = os.environ.get("GEMINI_API_KEY")

        if genai and self.api_key:
            try:
                self.model = genai.Client(api_key=self.api_key)
                print("[Planner] Gemini client initialized.")
            except Exception as e:
                print(f"[Planner] Failed to initialize Gemini client: {e}")
                self.model = None

        if not self.model and Llama and os.path.exists(self.model_path):
            print(f"[Planner] Loading local model from {self.model_path}...")
            self.llm = Llama(model_path=self.model_path, n_ctx=2048, verbose=False)
        elif not self.model:
            if not self.api_key:
                print("[Planner] GEMINI_API_KEY not found.")
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

        if self.model:  # model is a genai.Client instance
            return self._call_gemini_with_retry(scan_report)

        if self.llm:
            return self._call_local_llm(scan_report)

        return self._generate_mock_plan(scan_report)

    def _call_gemini_with_retry(self, scan_report):
        backoff = self.INITIAL_BACKOFF

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call_gemini(scan_report)
            except GeminiClientError as e:
                # 429 = quota/rate limit
                if hasattr(e, 'status_code') and e.status_code == 429:
                    if attempt == self.MAX_RETRIES - 1:
                        print(f"[Planner] Rate limit exceeded after {self.MAX_RETRIES} retries. Falling back to mock.")
                        logger.warning(f"Gemini rate limit: {e}")
                        return self._generate_mock_plan(scan_report)
                    wait_time = min(backoff, self.MAX_BACKOFF)
                    print(f"[Planner] Rate limited. Waiting {wait_time:.1f}s before retry {attempt + 2}/{self.MAX_RETRIES}...")
                    time.sleep(wait_time)
                    backoff *= self.BACKOFF_MULTIPLIER
                else:
                    print(f"[Planner] Gemini API error: {e}. Falling back to mock.")
                    logger.error(f"Gemini API error: {e}")
                    return self._generate_mock_plan(scan_report)
            except Exception as e:
                print(f"[Planner] Unexpected error: {e}. Falling back to mock.")
                logger.error(f"Unexpected error calling Gemini: {e}")
                return self._generate_mock_plan(scan_report)

        return self._generate_mock_plan(scan_report)

    def _call_gemini(self, scan_report):
        truncated = self._truncate_report(scan_report)
        prompt = (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"Here is the scan report:\n{json.dumps(truncated, indent=2)}"
        )

        print("[Planner] Querying Gemini for fix plan...")
        response = self.model.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        plan_text = response.text.strip()
        return {"status": "success", "plan": plan_text, "source": "gemini"}

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
        print("[Planner] Querying local LLM for fix plan...")
        prompt = self._build_prompt(scan_report)
        response = self.llm(prompt, max_tokens=512, stop=["</s>", "User:"], echo=False)
        raw_text = response['choices'][0]['text'].strip()
        return {"status": "success", "plan": raw_text, "source": "llama"}

    def _build_prompt(self, scan_report):
        findings = scan_report.get("findings", {})
        lint = findings.get("lint", [])
        dead = findings.get("dead_code", "")
        vulns = findings.get("vulnerabilities", [])

        prompt = "You are Ghost Committer, an autonomous AI developer agent. Create a concise, actionable plan to fix the following issues:\n\n"
        if lint:
            prompt += f"Linting Issues:\n{json.dumps(lint[:5], indent=2)}\n"
        if dead:
            prompt += f"Dead Code:\n{dead[:500]}\n"
        if vulns:
            prompt += f"Vulnerabilities:\n{json.dumps(vulns[:5], indent=2)}\n"
        prompt += "\nPlan of action:\n1."
        return prompt

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

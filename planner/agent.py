import json
import os
import time
import logging

logger = logging.getLogger(__name__)

try:
    from anthropic import Anthropic, RateLimitError, APIError
except ImportError:
    Anthropic = None
    RateLimitError = Exception
    APIError = Exception

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


class PlannerAgent:
    # Rate limiting configuration
    MAX_RETRIES = 5
    INITIAL_BACKOFF = 1.0  # seconds
    MAX_BACKOFF = 60.0  # seconds
    BACKOFF_MULTIPLIER = 2.0

    def __init__(self, model_path="models/phi-3-mini-4k-instruct.Q4_K_M.gguf"):
        self.model_path = model_path
        self.llm = None
        self.client = None
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

        # Try Anthropic Claude first
        if Anthropic and self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                print("[Planner] Anthropic client initialized.")
            except Exception as e:
                print(f"[Planner] Failed to initialize Anthropic client: {e}")
                self.client = None

        # Fall back to local LLM
        if not self.client and Llama and os.path.exists(self.model_path):
            print(f"[Planner] Loading local model from {self.model_path}...")
            # Increase context to 4096 for better file handling
            self.llm = Llama(model_path=self.model_path, n_ctx=4096, verbose=False)
        elif not self.client:
            if not self.api_key:
                print("[Planner] ANTHROPIC_API_KEY not found.")
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

        has_issues = any([
            lint_issues, dead_code, vulnerabilities,
            todos, complex_functions, missing_docstrings, previous_failure
        ])

        if not has_issues:
            return {"status": "success", "plan": "No issues found. Code is clean.", "source": "none"}

        # Try Anthropic Claude with rate limiting
        if self.client:
            return self._call_claude_with_retry(scan_report)

        # Try local LLM
        if self.llm:
            return self._call_local_llm(scan_report)

        # Fall back to mock
        return self._generate_mock_plan(scan_report)

    def _call_claude_with_retry(self, scan_report):
        """Call Claude API with exponential backoff for rate limiting."""
        backoff = self.INITIAL_BACKOFF

        for attempt in range(self.MAX_RETRIES):
            try:
                return self._call_claude(scan_report)
            except RateLimitError as e:
                if attempt == self.MAX_RETRIES - 1:
                    print(f"[Planner] Rate limit exceeded after {self.MAX_RETRIES} retries. Falling back to mock.")
                    logger.warning(f"Claude API rate limit exceeded: {e}")
                    return self._generate_mock_plan(scan_report)

                wait_time = min(backoff, self.MAX_BACKOFF)
                print(f"[Planner] Rate limited. Waiting {wait_time:.1f}s before retry {attempt + 2}/{self.MAX_RETRIES}...")
                time.sleep(wait_time)
                backoff *= self.BACKOFF_MULTIPLIER
            except APIError as e:
                print(f"[Planner] API error: {e}. Falling back to mock.")
                logger.error(f"Claude API error: {e}")
                return self._generate_mock_plan(scan_report)
            except Exception as e:
                print(f"[Planner] Unexpected error: {e}. Falling back to mock.")
                logger.error(f"Unexpected error calling Claude: {e}")
                return self._generate_mock_plan(scan_report)

        return self._generate_mock_plan(scan_report)

    def _call_claude(self, scan_report):
        """Make a single Claude API call."""
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

        # Truncate scan report to avoid token limits
        truncated_report = self._truncate_report(scan_report)
        user_message = f"Here is the scan report:\n{json.dumps(truncated_report, indent=2)}"

        print("[Planner] Querying Claude for fix plan...")
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=512,  # Reduced to save quota
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        plan_text = response.content[0].text.strip()
        return {"status": "success", "plan": plan_text, "source": "claude"}

    def _truncate_report(self, scan_report):
        """Truncate report to reduce token usage."""
        truncated = {
            "findings": {},
            "timestamp": scan_report.get("timestamp", ""),
        }

        findings = scan_report.get("findings", {})

        # Limit lint issues to first 10
        lint = findings.get("lint", [])
        if lint:
            truncated["findings"]["lint"] = lint[:10]
            if len(lint) > 10:
                truncated["findings"]["lint_total"] = len(lint)

        # Truncate dead code output
        dead_code = findings.get("dead_code", "")
        if dead_code:
            truncated["findings"]["dead_code"] = dead_code[:500]

        # Limit vulnerabilities to first 5
        vulns = findings.get("vulnerabilities", [])
        if vulns:
            truncated["findings"]["vulnerabilities"] = vulns[:5]
            if len(vulns) > 5:
                truncated["findings"]["vulnerabilities_total"] = len(vulns)

        # Include other fields with truncation
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
            stop=["</s>", "User:"],
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

        prompt = "You are Ghost Committer, an autonomous AI developer agent. Create a concise, actionable plan to fix the following issues:\n\n"
        if lint and isinstance(lint, list):
            prompt += f"Linting Issues:\n{json.dumps(lint[:5], indent=2)}\n"
        if dead:
            prompt += f"Dead Code:\n{dead[:500]}\n"
        if vulns and isinstance(vulns, list):
            prompt += f"Vulnerabilities:\n{json.dumps(vulns[:5], indent=2)}\n"
        elif isinstance(vulns, dict) and "error" in vulns:
             prompt += f"Vulnerabilities Error: {vulns['error']}\n"

        if todos and isinstance(todos, list):
            prompt += f"TODO Comments:\n{json.dumps(todos[:5], indent=2)}\n"
        if complex_funcs and isinstance(complex_funcs, list):
            prompt += f"Complex Functions:\n{json.dumps(complex_funcs[:5], indent=2)}\n"
        if missing_docs and isinstance(missing_docs, list):
            prompt += f"Missing Docstrings:\n{json.dumps(missing_docs[:5], indent=2)}\n"

        prompt += "\nPlan of action:\n1."
        return prompt

    def _generate_mock_plan(self, scan_report):
        """Generate a mock plan when APIs are unavailable."""
        # ... rest of mock plan ...

    def generate_patch(self, file_content, issue_description):
        """Generates a patch for a specific file and issue."""
        # Truncate issue description to avoid token limits
        truncated_issue = issue_description[:2000] if len(issue_description) > 2000 else issue_description
        print(f"[Planner] Generating patch for issue: {truncated_issue[:50]}...")
        
        prompt = (
            "<|system|>\n"
            "You are a Python Code Generator. Your task is to output the FULL, updated content of a Python file. "
            "STRICT RULES:\n"
            "1. Output ONLY the code.\n"
            "2. DO NOT use markdown code blocks (no ```).\n"
            "3. DO NOT include explanations, greetings, or conversational filler.\n"
            "4. Maintain all existing imports and functionality unless specifically asked to change them.\n"
            "5. If you fail to follow these rules, the system will break.\n"
            "<|user|>\n"
            f"--- ORIGINAL FILE CONTENT ---\n{file_content}\n\n"
            f"--- ISSUE TO FIX ---\n{truncated_issue}\n\n"
            "Provide the complete updated Python file content now.\n"
            "<|assistant|>\n"
        )

        raw_patch = ""
        if self.client:
             response = self.client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=2048,
                system="Output only raw file content.",
                messages=[{"role": "user", "content": prompt}],
            )
             raw_patch = response.content[0].text.strip()
        
        elif self.llm:
            response = self.llm(
                prompt,
                max_tokens=2048,
                stop=["<|end|>", "<|user|>", "<|system|>", "---"],
                echo=False
            )
            raw_patch = response['choices'][0]['text'].strip()
        
        if not raw_patch:
            return file_content

        # Advanced cleaning of LLM artifacts
        lines = raw_patch.splitlines()
        clean_lines = []
        
        # Stop words that indicate the LLM started talking instead of coding
        stop_phrases = ["here is the", "updated file", "i have", "assistant:", "python", "```"]
        
        for line in lines:
            trimmed = line.strip().lower()
            # Skip empty lines at the very beginning
            if not clean_lines and not trimmed:
                continue
            # If we hit a markdown block or conversational filler, skip it
            if any(phrase in trimmed for phrase in stop_phrases) and len(trimmed) < 100:
                continue
            clean_lines.append(line)
            
        # Join and perform a final check
        final_code = "\n".join(clean_lines).strip()
        
        # If the LLM just repeated the prompt or returned something too short, fallback
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

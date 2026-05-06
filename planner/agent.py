import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


class PlannerAgent:
    OPENCODE_GO_CHAT_URL = "https://opencode.ai/zen/go/v1/chat/completions"
    OPENCODE_GO_MESSAGES_URL = "https://opencode.ai/zen/go/v1/messages"
    OPENCODE_GO_MESSAGE_MODELS = {"minimax-m2.5", "minimax-m2.7"}
    OPENCODE_GO_MODEL_ALIASES = {
        "mimo v2.5": "opencode-go/mimo-v2.5",
        "mimo v2.5 pro": "opencode-go/mimo-v2.5-pro",
        "minimax m2.5": "opencode-go/minimax-m2.5",
        "minimax m2.7": "opencode-go/minimax-m2.7",
        "qwen3.5 plus": "opencode-go/qwen3.5-plus",
        "deepseek v4 flash": "opencode-go/deepseek-v4-flash",
        "deepseek v4 pro": "opencode-go/deepseek-v4-pro",
        "glm-5.1": "opencode-go/glm-5.1",
        "glm 5.1": "opencode-go/glm-5.1",
        "kimi k2.5": "opencode-go/kimi-k2.5",
        "kimi k2.6": "opencode-go/kimi-k2.6",
        "kimi k2.6 (3x limits)": "opencode-go/kimi-k2.6",
        "mimo v2 omni": "opencode-go/mimo-v2-omni",
    }

    SYSTEM_PROMPT = (
        "You are a senior software engineer specializing in code quality. "
        "You will be given a JSON scan report of a Python codebase. "
        "Produce a concise numbered fix plan."
    )

    def __init__(self, model_path="models/phi-3-mini-4k-instruct.Q4_K_M.gguf"):
        self.model_path = model_path
        self.llm = None
        self.api_key = os.environ.get("OPENCODE_API_KEY")
        self.opencode_model = self._normalize_model_name(
            os.environ.get("OPENCODE_MODEL", "opencode-go/kimi-k2.6")
        )
        self.opencode_base_url = os.environ.get("OPENCODE_BASE_URL") or self._default_opencode_url(
            self.opencode_model
        )
        self.opencode_timeout = float(os.environ.get("OPENCODE_TIMEOUT_SECONDS", "90"))

        if self.api_key:
            print(f"[Planner] OpenCode Go planner configured with model {self.opencode_model}.")
        elif Llama and os.path.exists(self.model_path):
            print(f"[Planner] Loading local model from {self.model_path}...")
            self.llm = Llama(model_path=self.model_path, n_ctx=2048, verbose=False)
        else:
            print("[Planner] OPENCODE_API_KEY not found.")
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

        if self.api_key:
            return self._call_opencode_with_fallback(scan_report)

        if self.llm:
            return self._call_local_llm(scan_report)

        return self._generate_mock_plan(scan_report)

    def _normalize_model_name(self, model_name):
        name = model_name.strip()
        if name.startswith("opencode-go/"):
            return name
        key = " ".join(name.lower().replace("_", " ").replace("-", " ").split())
        return self.OPENCODE_GO_MODEL_ALIASES.get(key, f"opencode-go/{name}")

    def _api_model_name(self, model_name):
        return model_name.removeprefix("opencode-go/")

    def _default_opencode_url(self, model_name):
        model = self._api_model_name(model_name)
        if model in self.OPENCODE_GO_MESSAGE_MODELS:
            return self.OPENCODE_GO_MESSAGES_URL
        return self.OPENCODE_GO_CHAT_URL

    def _call_opencode_with_fallback(self, scan_report):
        truncated = self._truncate_report(scan_report)
        report_json = json.dumps(truncated, indent=2)
        model = self._api_model_name(self.opencode_model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.opencode_base_url.endswith("/messages"):
            payload = {
                "model": model,
                "max_tokens": 800,
                "system": self.SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": f"Here is the scan report:\n{report_json}"}],
            }
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Here is the scan report:\n{report_json}"},
                ],
            }

        try:
            print(f"[Planner] Querying OpenCode Go model {self.opencode_model}...")
            response = requests.post(
                self.opencode_base_url,
                headers=headers,
                json=payload,
                timeout=self.opencode_timeout,
            )
            response.raise_for_status()
            plan_text = self._extract_opencode_text(response.json()).strip()
            if not plan_text:
                raise ValueError("OpenCode returned an empty response.")
            return {"status": "success", "plan": plan_text, "source": "opencode-go", "model": self.opencode_model}
        except Exception as e:
            detail = ""
            if isinstance(e, requests.HTTPError) and e.response is not None:
                detail = f" Response: {e.response.text[:500]}"
            print(f"[Planner] OpenCode Go planner error: {e}.{detail} Falling back to mock.")
            logger.error(f"OpenCode Go planner error: {e}.{detail}")
            return self._generate_mock_plan(scan_report)

    def _extract_opencode_text(self, data):
        if data.get("choices"):
            content = data["choices"][0].get("message", {}).get("content", "")
            if isinstance(content, str):
                return content
        if data.get("content"):
            return "\n".join(part.get("text", "") for part in data["content"] if part.get("text"))
        if data.get("output_text"):
            return data["output_text"]
        raise ValueError("OpenCode response did not contain text output.")

    def _truncate_report(self, scan_report):
        findings = scan_report.get("findings", {})
        truncated = {"findings": {}, "timestamp": scan_report.get("timestamp", "")}
        for key, limit in [("lint", 10), ("vulnerabilities", 5)]:
            value = findings.get(key, [])
            if isinstance(value, list) and value:
                truncated["findings"][key] = value[:limit]
                if len(value) > limit:
                    truncated["findings"][f"{key}_total"] = len(value)
        if findings.get("dead_code"):
            truncated["findings"]["dead_code"] = findings["dead_code"][:500]
        if scan_report.get("previous_failure"):
            truncated["previous_failure"] = str(scan_report["previous_failure"])[:300]
        return truncated

    def _call_local_llm(self, scan_report):
        print("[Planner] Querying local LLM for fix plan...")
        prompt = self._build_prompt(scan_report)
        response = self.llm(prompt, max_tokens=512, stop=["</s>", "User:"], echo=False)
        return {"status": "success", "plan": response["choices"][0]["text"].strip(), "source": "llama"}

    def _build_prompt(self, scan_report):
        return (
            "Create a concise, actionable plan to fix this scan report:\n\n"
            f"{json.dumps(self._truncate_report(scan_report), indent=2)}\n\nPlan:\n1."
        )

    def _generate_mock_plan(self, scan_report):
        findings = scan_report.get("findings", {})
        plan_lines = ["MOCK PLAN:"]
        step = 1
        if findings.get("lint"):
            plan_lines.append(f"{step}. Fix {len(findings['lint'])} lint issues.")
            step += 1
        if findings.get("dead_code"):
            plan_lines.append(f"{step}. Remove dead code.")
            step += 1
        if findings.get("vulnerabilities"):
            plan_lines.append(f"{step}. Update dependencies to patch {len(findings['vulnerabilities'])} vulnerabilities.")
            step += 1
        if scan_report.get("previous_failure"):
            plan_lines.append(f"{step}. Address previous test failure before re-applying fixes.")
        return {"status": "mock", "plan": "\n".join(plan_lines), "source": "mock"}


if __name__ == "__main__":
    planner = PlannerAgent()
    dummy_report = {"findings": {"lint": [{"message": "Unused import"}], "dead_code": "", "vulnerabilities": []}}
    print(json.dumps(planner.generate_plan(dummy_report), indent=2))

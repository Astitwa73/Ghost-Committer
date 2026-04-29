import json
import os
try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

class PlannerAgent:
    def __init__(self, model_path="models/phi-3-mini-4k-instruct.Q4_K_M.gguf"):
        self.model_path = model_path
        self.llm = None
        
        # In a real environment, we would download the model to this path.
        if Llama and os.path.exists(self.model_path):
            print(f"[Planner] Loading model from {self.model_path}...")
            self.llm = Llama(model_path=self.model_path, n_ctx=2048, verbose=False)
        else:
            print(f"[Planner] Model not found at {self.model_path}. Running in mock mode.")

    def generate_plan(self, scan_report):
        """Analyzes scan report and plans fixes."""
        print("[Planner] Analyzing scan report...")
        
        lint_issues = scan_report.get("findings", {}).get("lint", [])
        dead_code = scan_report.get("findings", {}).get("dead_code", "")
        vulnerabilities = scan_report.get("findings", {}).get("vulnerabilities", [])
        
        if not (lint_issues or dead_code or vulnerabilities):
             return {"status": "success", "plan": "No issues found. Code is clean."}

        prompt = self._build_prompt(lint_issues, dead_code, vulnerabilities)
        
        if self.llm:
            print("[Planner] Querying LLM for fix plan...")
            response = self.llm(
                prompt,
                max_tokens=512,
                stop=["</s>", "User:"],
                echo=False
            )
            raw_text = response['choices'][0]['text'].strip()
            return {"status": "success", "plan": raw_text}
        else:
            # Mock behavior for testing pipeline without huge downloads
            return {
                "status": "mock", 
                "plan": f"MOCK PLAN:\n1. Fix {len(lint_issues)} lint issues.\n2. Remove dead code.\n3. Update dependencies to patch vulnerabilities."
            }
            
    def _build_prompt(self, lint, dead, vulns):
        # Prompt to instruct the LLM
        prompt = "You are Ghost Committer, an autonomous AI developer agent. Create a concise, actionable plan to fix the following issues:\n\n"
        if lint:
             prompt += f"Linting Issues:\n{json.dumps(lint[:5], indent=2)}\n" # Cap at 5 to save context
        if dead:
             prompt += f"Dead Code:\n{dead[:500]}\n"
        if vulns:
             prompt += f"Vulnerabilities:\n{json.dumps(vulns, indent=2)}\n"
             
        prompt += "\nPlan of action:\n1."
        return prompt

if __name__ == "__main__":
    planner = PlannerAgent()
    dummy_report = {
        "findings": {
            "lint": [{"message": "Unused import sys", "filename": "main.py", "location": {"row": 1}}],
            "dead_code": "main.py:10: unused function 'old_helper'",
            "vulnerabilities": []
        }
    }
    print(json.dumps(planner.generate_plan(dummy_report), indent=2))

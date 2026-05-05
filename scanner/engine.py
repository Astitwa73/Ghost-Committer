import subprocess
import json
import os

class CodeScanner:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        _root = os.path.dirname(os.path.dirname(__file__))
        _bin = "Scripts" if os.name == "nt" else "bin"
        self.venv_bin = os.path.join(_root, ".venv", _bin)

    def _get_cmd_path(self, cmd):
        """Helper to get the full path of a command in the venv."""
        ext = ".exe" if os.name == "nt" else ""
        full_path = os.path.join(self.venv_bin, f"{cmd}{ext}")
        return full_path if os.path.exists(full_path) else cmd

    def run_ruff(self):
        """Runs ruff linter and returns findings."""
        cmd = self._get_cmd_path("ruff")
        print(f"[Scanner] Running {cmd} on {self.repo_path}...")
        try:
            result = subprocess.run(
                [cmd, "check", self.repo_path, "--output-format", "json"],
                capture_output=True,
                text=True,
                check=False
            )
            return json.loads(result.stdout) if result.stdout else []
        except Exception as e:
            return {"error": str(e)}

    def run_vulture(self):
        """Runs vulture to find dead code."""
        cmd = self._get_cmd_path("vulture")
        print(f"[Scanner] Running {cmd} on {self.repo_path}...")
        try:
            result = subprocess.run(
                [cmd, self.repo_path],
                capture_output=True,
                text=True,
                check=False
            )
            return result.stdout
        except Exception as e:
            return str(e)

    def run_pip_audit(self):
        """Runs pip-audit for dependency vulnerabilities."""
        cmd = self._get_cmd_path("pip-audit")
        print(f"[Scanner] Running {cmd} on {self.repo_path}...")
        try:
            req_path = os.path.join(self.repo_path, "requirements.txt")
            if not os.path.exists(req_path):
                return {"error": "requirements.txt not found"}
            result = subprocess.run(
                [cmd, "-r", req_path, "--format", "json"],
                capture_output=True,
                text=True,
                check=False
            )
            return json.loads(result.stdout) if result.stdout else []
        except Exception as e:
            return {"error": str(e)}

if __name__ == "__main__":
    # Test on itself for now
    scanner = CodeScanner(".")
    print("--- RUFF FINDINGS ---")
    print(scanner.run_ruff())

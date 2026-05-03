import subprocess
import json
import os

class CodeScanner:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.venv_bin = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv", "Scripts")

    def _get_cmd_path(self, cmd):
        """Helper to get the full path of a command in the venv."""
        full_path = os.path.join(self.venv_bin, f"{cmd}.exe")
        return full_path if os.path.exists(full_path) else cmd

    def run_ruff(self):
        """Runs ruff linter and returns findings."""
        cmd = self._get_cmd_path("ruff")
        print(f"[Scanner] Running {cmd} on {self.repo_path}...")
        try:
            result = subprocess.run(
                [cmd, "check", self.repo_path, "--format", "json", "--exclude", ".venv"],
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
        print(f"[Scanner] Running {cmd} on {self.repo_path} --exclude .venv...")
        try:
            result = subprocess.run(
                [cmd, self.repo_path, "--exclude", ".venv"],
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
            if not result.stdout:
                return []
            
            data = json.loads(result.stdout)
            vulns = []
            if "dependencies" in data:
                for dep in data["dependencies"]:
                    if dep.get("vulns"):
                        for v in dep["vulns"]:
                            vulns.append({
                                "package": dep.get("name"),
                                "version": dep.get("version"),
                                "id": v.get("id"),
                                "description": v.get("description")
                            })
            return vulns
        except Exception as e:
            return {"error": str(e)}

    def scan_todos(self):
        """Finds TODO and FIXME comments."""
        print(f"[Scanner] Scanning for TODOs in {self.repo_path}...")
        todos = []
        for root, dirs, files in os.walk(self.repo_path):
            if ".venv" in dirs:
                dirs.remove(".venv")
            if ".git" in dirs:
                dirs.remove(".git")
            
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            for i, line in enumerate(f, 1):
                                if "TODO:" in line or "FIXME:" in line:
                                    todos.append({
                                        "file": os.path.relpath(path, self.repo_path),
                                        "line": i,
                                        "content": line.strip()
                                    })
                    except Exception:
                        continue
        return todos

    def scan_complex_functions(self):
        """Identify potentially complex functions (simple heuristic)."""
        print(f"[Scanner] Scanning for complex functions in {self.repo_path}...")
        complex_funcs = []
        for root, dirs, files in os.walk(self.repo_path):
            if ".venv" in dirs:
                dirs.remove(".venv")
            
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Simple heuristic: count 'if', 'for', 'while' inside a function
                            # Real implementation would use AST
                            lines = content.splitlines()
                            current_func = None
                            complexity = 0
                            for i, line in enumerate(lines, 1):
                                if line.strip().startswith("def "):
                                    if current_func and complexity > 3:
                                        complex_funcs.append(current_func)
                                    current_func = {"name": line.split("(")[0].replace("def ", "").strip(), "file": os.path.relpath(path, self.repo_path), "line": i}
                                    complexity = 0
                                elif current_func:
                                    complexity += line.count(" if ") + line.count(" for ") + line.count(" while ")
                            if current_func and complexity > 3:
                                complex_funcs.append(current_func)
                    except Exception:
                        continue
        return complex_funcs

    def scan_missing_docstrings(self):
        """Finds functions missing docstrings."""
        print(f"[Scanner] Scanning for missing docstrings in {self.repo_path}...")
        missing = []
        for root, dirs, files in os.walk(self.repo_path):
            if ".venv" in dirs:
                dirs.remove(".venv")
            
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines):
                                if line.strip().startswith("def "):
                                    # Check next line for docstring
                                    if i + 1 < len(lines):
                                        next_line = lines[i+1].strip()
                                        if not (next_line.startswith('"""') or next_line.startswith("'''")):
                                            missing.append({
                                                "name": line.split("(")[0].replace("def ", "").strip(),
                                                "file": os.path.relpath(path, self.repo_path),
                                                "line": i + 1
                                            })
                    except Exception:
                        continue
        return missing

if __name__ == "__main__":
    # Test on itself for now
    scanner = CodeScanner(".")
    print("--- RUFF FINDINGS ---")
    print(scanner.run_ruff())

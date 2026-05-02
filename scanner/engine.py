import subprocess
import json
import os
import ast

class CodeScanner:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.venv_bin = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv", "Scripts")

    def _get_cmd_path(self, cmd):
        """Helper to get the full path of a command in the venv."""
        full_path = os.path.join(self.venv_bin, f"{cmd}.exe")
        return full_path if os.path.exists(full_path) else cmd

    def _should_skip_dir(self, dirname):
        """Skip common non-source directories."""
        skip = {".venv", "venv", "__pycache__", ".git", ".pytest_cache", "node_modules", ".tox"}
        return dirname in skip or dirname.startswith(".")

    def run_ruff(self):
        """Runs ruff linter and returns findings."""
        cmd = self._get_cmd_path("ruff")
        print(f"[Scanner] Running {cmd} on {self.repo_path}...")
        try:
            result = subprocess.run(
                [cmd, "check", self.repo_path, "--format", "json"],
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

    def find_todos(self):
        """Walk all .py files and find TODO/FIXME comments."""
        print(f"[Scanner] Scanning for TODOs in {self.repo_path}...")
        todos = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        for line_no, line in enumerate(f, start=1):
                            if "# TODO" in line or "# FIXME" in line:
                                todos.append({
                                    "file": fpath,
                                    "line": line_no,
                                    "text": line.rstrip("\n")
                                })
                except Exception as e:
                    print(f"[Scanner] Could not read {fpath}: {e}")
        return todos

    def find_complex_functions(self):
        """Use AST to find functions with 3+ nested If nodes."""
        print(f"[Scanner] Scanning for complex functions in {self.repo_path}...")
        flagged = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            nested_if_count = 0
                            for child in ast.walk(node):
                                if isinstance(child, ast.If) and child is not node:
                                    nested_if_count += 1
                            if nested_if_count >= 3:
                                flagged.append({
                                    "file": fpath,
                                    "function": node.name,
                                    "nesting_depth": nested_if_count
                                })
                except Exception as e:
                    print(f"[Scanner] Could not parse {fpath}: {e}")
        return flagged

    def find_missing_docstrings(self):
        """Use AST to find exported functions missing docstrings."""
        print(f"[Scanner] Scanning for missing docstrings in {self.repo_path}...")
        flagged = []
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.name.startswith("__"):
                                continue
                            has_docstring = False
                            if node.body:
                                first_stmt = node.body[0]
                                if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Constant) and isinstance(first_stmt.value.value, str):
                                    has_docstring = True
                            if not has_docstring:
                                flagged.append({
                                    "file": fpath,
                                    "function": node.name,
                                    "line": node.lineno
                                })
                except Exception as e:
                    print(f"[Scanner] Could not parse {fpath}: {e}")
        return flagged

if __name__ == "__main__":
    scanner = CodeScanner(".")
    print("--- RUFF FINDINGS ---")
    print(scanner.run_ruff())
    print("\n--- TODOS ---")
    print(scanner.find_todos())
    print("\n--- COMPLEX FUNCTIONS ---")
    print(scanner.find_complex_functions())
    print("\n--- MISSING DOCSTRINGS ---")
    print(scanner.find_missing_docstrings())

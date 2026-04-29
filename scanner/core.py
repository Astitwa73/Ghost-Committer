from .engine import CodeScanner
import datetime

class ScannerCore:
    def __init__(self, repo_path):
        self.scanner = CodeScanner(repo_path)
        self.report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "repo_path": repo_path,
            "findings": {
                "lint": [],
                "dead_code": "",
                "vulnerabilities": []
            }
        }

    def generate_full_report(self):
        """Runs all scans and aggregates results."""
        print(f"[ScannerCore] Starting full scan of {self.scanner.repo_path}...")
        
        # 1. Linting
        self.report["findings"]["lint"] = self.scanner.run_ruff()
        
        # 2. Dead Code
        self.report["findings"]["dead_code"] = self.scanner.run_vulture()
        
        # 3. Vulnerabilities
        self.report["findings"]["vulnerabilities"] = self.scanner.run_pip_audit()
        
        return self.report

if __name__ == "__main__":
    core = ScannerCore(".")
    report = core.generate_full_report()
    
    print("\n--- GHOST COMMITTER SCAN REPORT ---")
    print(f"Time: {report['timestamp']}")
    print(f"Lint issues: {len(report['findings']['lint'])}")
    print(f"Vulnerabilities: {len(report['findings']['vulnerabilities'])}")
    if report['findings']['dead_code']:
        print("Dead code detected.")

import docker
import os

class SandboxValidator:
    def __init__(self, repo_path):
        self.repo_path = os.path.abspath(repo_path)
        try:
            self.client = docker.from_env()
        except Exception as e:
            print(f"[Validator] Could not connect to Docker daemon: {e}")
            self.client = None

    def run_tests(self, image="python:3.11-slim", test_command="python -m unittest discover"):
        """Spins up a sandbox and runs the test suite."""
        if not self.client:
             return {"status": "error", "message": "Docker not available."}
             
        print(f"[Validator] Starting sandbox using image '{image}'...")
        try:
            # We mount the repo to /app in the container
            volumes = {
                self.repo_path: {'bind': '/app', 'mode': 'rw'}
            }
            
            # For this MVP, we install requirements and run tests.
            # In a real scenario, this would read from a SKILL.md or detect project type.
            full_cmd = f"sh -c 'cd /app && pip install -r requirements.txt --quiet && {test_command}'"
            
            container = self.client.containers.run(
                image,
                full_cmd,
                volumes=volumes,
                working_dir="/app",
                detach=False,
                remove=True # Auto-cleanup
            )
            
            print("[Validator] Tests passed successfully in sandbox.")
            return {"status": "success", "output": container.decode('utf-8')}
            
        except docker.errors.ContainerError as e:
            print("[Validator] Tests FAILED in sandbox.")
            return {"status": "failed", "output": e.stderr.decode('utf-8')}
        except Exception as e:
            print(f"[Validator] Sandbox execution error: {e}")
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    validator = SandboxValidator(".")
    result = validator.run_tests()
    print(result)

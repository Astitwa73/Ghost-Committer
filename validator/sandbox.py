import os
import sys
import subprocess

try:
    import docker
except ImportError:
    docker = None


class SandboxValidator:
    def __init__(self, repo_path):
        self.repo_path = os.path.abspath(repo_path)
        self.client = None
        if docker is None:
            print("[Validator] docker-py not installed. Will use local fallback.")
            return
        try:
            self.client = docker.from_env()
            self.client.ping()
            print("[Validator] Docker is available.")
        except Exception as e:
            print(f"[Validator] Docker unavailable: {e}. Will use local fallback.")
            self.client = None

    def run_tests(self, image="python:3.11-slim", test_command="python -m unittest discover"):
        """Spins up a sandbox and runs the test suite, with local fallback."""
        if self.client:
            return self._run_docker_tests(image, test_command)
        else:
            return self._run_local_tests()

    def _run_docker_tests(self, image, test_command):
        """Run tests inside Docker container with optimized build logic."""
        print("[Validator] Running tests in Docker sandbox...")
        
        # Optimization: Check if we have a pre-cached image to avoid apt-get
        custom_image = "ghost-validator:latest"
        try:
            self.client.images.get(custom_image)
            image = custom_image
            print(f"[Validator] Using optimized local image: {image}")
            # If using custom image, we only need to install requirements and run tests
            full_cmd = (
                "sh -c 'pip install -r requirements.txt && "
                "python -m unittest discover -s . -p test_*.py'"
            )
        except Exception:
            print("[Validator] Optimized image not found. Performing full setup (slow)...")
            full_cmd = (
                "sh -c 'apt-get update && apt-get install -y git build-essential && "
                "pip install --upgrade pip && "
                "pip install -r requirements.txt && "
                "python -m unittest discover -s . -p test_*.py'"
            )

        volumes = {self.repo_path: {"bind": "/app", "mode": "rw"}}
        container = None
        try:
            container = self.client.containers.run(
                image,
                full_cmd,
                volumes=volumes,
                working_dir="/app",
                detach=True,
            )
            result = container.wait(timeout=300)
            logs = container.logs().decode("utf-8", errors="replace")

            # Extract ONLY the test failure part for cleaner logs/LLM feedback
            test_output = ""
            if "Ran " in logs:
                test_output = logs[logs.find("Ran "):]
            else:
                test_output = logs[-2000:] # Fallback to last 2k chars

            exit_code = result.get("StatusCode", -1)
            if exit_code == 0 and "FAILED" not in logs and "Error" not in logs:
                print("[Validator] Tests passed in Docker sandbox.")
                return {"status": "success", "output": test_output}
            else:
                print("[Validator] Tests FAILED in Docker sandbox.")
                # We return the extracted test output to avoid sending 500k chars of apt-get logs to the LLM
                return {"status": "failed", "output": test_output}
        except Exception as e:
            if req and hasattr(req, 'exceptions') and 'ReadTimeout' in str(type(e)):
                print("[Validator] Docker sandbox timed out after 5 minutes.")
                return {"status": "failed", "output": "Docker sandbox timed out."}
            print(f"[Validator] Docker error: {e}")
            return {"status": "failed", "output": str(e)}
        finally:
            if container:
                try:
                    container.stop(timeout=10)
                    container.remove(force=True)
                except Exception:
                    pass

    def _run_local_tests(self):
        """Run tests locally when Docker is unavailable."""
        print("[Validator] Running tests locally (Docker fallback)...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", self.repo_path, "-p", "test_*.py"],
                capture_output=True,
                text=True,
                check=False,
                cwd=self.repo_path,
            )
            output = result.stdout + "\n" + result.stderr
            output = output.strip()
            print("[Validator] Local test execution complete.")

            if result.returncode != 0 or "FAILED" in output or "Error" in output:
                print("[Validator] Tests FAILED locally.")
                return {"status": "failed", "output": output}
            else:
                print("[Validator] Tests passed locally.")
                return {"status": "success", "output": output}
        except Exception as e:
            print(f"[Validator] Local test error: {e}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    validator = SandboxValidator(".")
    result = validator.run_tests()
    print(result)

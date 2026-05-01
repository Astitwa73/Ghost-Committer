# 👻 Ghost Committer

**The autonomous overnight engineer for your tech debt.**

Ghost Committer is an autonomous, on-prem AI agent designed to run while your developers sleep. It cleans up tech debt, patches known vulnerabilities, removes dead code, runs your test suite in an isolated Docker sandbox, and opens a Pull Request by morning. 

Built for the **Samsung PRISM OpenClaw Platform Hackathon (2026)**.

---

## 🏗️ Architecture & Pipeline

Ghost Committer operates on a strict **5-Layer Pipeline** to ensure that no broken code is ever merged and that your proprietary source code never leaves your local network.

1. **Scanner (L2):** Analyzes the codebase using static analysis tools (`ruff`, `vulture`, `pip-audit`) to identify linting issues, dead code, and dependency vulnerabilities.
2. **Planner (L3):** Uses a local, quantized LLM (via `llama.cpp`) to digest the scan report and generate a concrete, actionable plan to fix the identified issues.
3. **Patcher (L4):** Uses `GitPython` to automatically create a new branch (e.g., `chore/ghost-auto-...`), apply the code edits suggested by the Planner, and commit the changes.
4. **Validator (L5):** Spins up an ephemeral Docker container ("The Sandbox") using `docker-py`, mounts the repository, and runs the project's test suite. *If the tests fail, the pipeline stops.*
5. **Delivery (L6):** If the tests pass, uses `PyGithub` to push the branch and open a Pull Request. It then uses `slack_sdk` to send a "Morning Digest" to the engineering team.

---

## 📁 Directory Structure

*   **`scanner/`** 
    *   `engine.py`: Wrappers around shell commands to execute `ruff`, `vulture`, and `pip-audit`.
    *   `core.py`: Aggregates the findings from the engine into a unified JSON `Scan Report`.
*   **`planner/`**
    *   `agent.py`: Interfaces with the local LLM. Takes the `Scan Report` and prompts the model to generate a fix strategy. *Defaults to a mock plan if no model is found.*
*   **`patcher/`**
    *   `git_ops.py`: Handles all Git operations: creating branches, staging modified files, and committing.
*   **`validator/`**
    *   `sandbox.py`: Connects to the local Docker daemon. Creates a container, mounts the repo, installs dependencies, and runs `python -m unittest discover` (or your configured test runner) to verify the patch.
*   **`delivery/`**
    *   `github_ops.py`: Uses `GITHUB_TOKEN` to interact with the GitHub API to open the final PR.
    *   `slack_notify.py`: Uses `SLACK_BOT_TOKEN` to send a summary of the overnight work to a configured Slack channel.
*   **`main.py`**
    *   The primary orchestrator script that ties all layers together sequentially.
*   **`requirements.txt`**
    *   Core Python dependencies (FastAPI, PyGithub, docker, llama-cpp-python, tree-sitter, etc.).

---

## 🚀 How to Run

### Prerequisites
1.  **Python 3.10+** installed.
2.  **Docker Desktop** installed and running (required for the Validator layer).
3.  **Local LLM:** Download a GGUF model (e.g., Llama 3 or Phi-3) and place it in a `models/` directory if you want real code generation (otherwise it runs in "mock" mode).

### Setup

1.  **Activate the Virtual Environment:**
    ```powershell
    .\.venv\Scripts\Activate.ps1
    ```
2.  **(Optional) Set Environment Variables for Delivery:**
    If these are not set, the delivery layer will run in "dry-run" mode (it will print what it *would* do to the console).
    ```powershell
    $env:GITHUB_TOKEN="your_github_pat"
    $env:GITHUB_REPOSITORY="your_username/your_repo"
    $env:SLACK_BOT_TOKEN="xoxb-your-slack-token"
    $env:SLACK_CHANNEL="#engineering"
    ```

### Execution

To run the agent manually (or configure this to run via a Cron job / OpenClaw Heartbeat):

```powershell
python main.py
```

*You can also point it at a specific repository directory:*
```powershell
python main.py "C:\path\to\another\repo"
```

## 🔮 Future Enhancements
*   Integrate AST parsing (`tree-sitter`) into the Scanner to intelligently remove dead functions without breaking imports.
*   Implement automatic minor-version bumping for known CVEs.
*   Expand the Validator to read a `SKILL.md` file to determine the correct test commands for different languages (Node.js, Rust, Go).

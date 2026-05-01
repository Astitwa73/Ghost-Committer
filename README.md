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

## 🛠️ Current Status: Partially Operational

As of **May 1, 2026**, the following layers are fully functional:
- ✅ **Scanner (L2):** `ruff`, `vulture`, and `pip-audit` are integrated and reporting correctly.
- ✅ **Planner (L3):** Operates in **Mock Mode** (generates a standard cleanup plan).
- ✅ **Patcher (L4):** Robust branching, staging, and committing logic is implemented. Now supports automatic return to the original branch on failure.
- ✅ **Delivery (L6):** Slack notification syntax fixed. Dry-run mode works; PR creation requires a valid `GITHUB_TOKEN`.

**Blocked Layer:**
- ❌ **Validator (L5):** Requires **Docker Desktop** to be running to create the "Sandbox" container for test execution.

---

## 🚀 Setup & Execution

### 1. Prerequisites
*   **Python 3.10+**
*   **Git:** Must be installed and configured in your system PATH.
*   **Docker Desktop (CRITICAL):** Must be running for the Validator layer to pass.

### 2. Installation
1.  **Clone the Repository.**
2.  **Initialize the Virtual Environment:**
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```
3.  **Install Dependencies:**
    ```powershell
    pip install -r requirements.txt
    ```
    *(Note: Key libraries like `GitPython`, `PyGithub`, and `docker-py` are now required).*

### 3. Environment Configuration
Create a `.env` file or set the following in your shell:
```powershell
$env:GITHUB_TOKEN="your_pat_here"
$env:GITHUB_REPOSITORY="username/repo"
$env:SLACK_BOT_TOKEN="xoxb-..."
$env:SLACK_CHANNEL="#engineering"
```

### 4. Running the Agent
```powershell
python main.py
```

---

## 🗺️ Roadmap & Next Steps (Detailed)

### Phase 1: Infrastructure (Immediate)
1.  **Docker Integration:** Ensure Docker is accessible to the Python environment. The agent needs to be able to run `docker ps` without errors.
2.  **LLM Setup:**
    *   Create a `models/` folder.
    *   Download a GGUF model (e.g., `phi-3-mini-4k-instruct.Q4_K_M.gguf`).
    *   Update the path in `planner/agent.py` to enable real AI-driven patching instead of "Mock Mode."

### Phase 2: OpenClaw Integration
1.  **Manifest Creation:** Create an `openclaw.yaml` file to define the agent's schedule and resource requirements for the Samsung PRISM platform.
2.  **SDK Integration:** Implement the `OpenClaw Heartbeat` in `main.py` to allow the platform to monitor the agent's overnight progress.

### Phase 3: Advanced Intelligence
1.  **AST Refinement:** Use the already-installed `tree-sitter` library to move beyond simple string replacement and perform intelligent code refactoring.
2.  **Multi-Language Validation:** Expand `validator/sandbox.py` to auto-detect the project type (Node, Go, Python) and run the appropriate test suite.


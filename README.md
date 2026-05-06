# 👻 Ghost Committer

**The autonomous overnight engineer for your tech debt.**

Ghost Committer is an autonomous, on-prem AI agent designed to run while your developers sleep. It cleans up tech debt, patches known vulnerabilities, removes dead code, runs your test suite in an isolated Docker sandbox, and opens a Pull Request by morning. 

Built for the **Samsung PRISM OpenClaw Platform (2026)**.

---

## 🏗️ Architecture & Pipeline

Ghost Committer operates on a strict **5-Layer Pipeline** with an integrated **Self-Correction Loop** to ensure high-quality code delivery.

1. **Scanner (L2):** Analyzes the codebase using `ruff`, `vulture`, and `pip-audit` to identify linting issues, dead code, and security vulnerabilities. It also uses custom AST scans for TODOs, complex functions, and missing docstrings.
2. **Planner (L3):** Uses a local, quantized LLM (Phi-3 via `llama.cpp`) or Anthropic Claude to analyze the scan report and generate concrete code patches.
3. **Patcher (L4):** Automatically creates a new branch and applies **real code edits** suggested by the Planner. It iterates through all found issues (docstrings, TODOs, complex code) in a single session.
4. **Validator (L5):** Spins up an optimized Docker Sandbox (`ghost-validator:latest`) to run tests. 
    *   **Self-Correction Loop:** If tests fail, the agent captures the error logs, sends them back to the Planner for a corrected patch, and retries up to 3 times automatically.
5. **Delivery (L6):** Upon successful validation, it pushes the branch, opens a GitHub Pull Request, and sends a "Morning Digest" to Slack and Telegram.

---

## 📁 Directory Structure

*   **`scanner/`**: Static analysis engine (Ruff, Vulture, Pip-Audit, AST).
*   **`planner/`**: LLM interface (Local Phi-3 / Claude-3.5) with advanced prompt engineering.
*   **`patcher/`**: Git operations and autonomous file modification logic.
*   **`validator/`**: Docker sandbox management with pre-cached system tools.
*   **`delivery/`**: GitHub API integration and notification handlers.
*   **`scheduler.py`**: The 2 AM automation script that triggers the pipeline daily.
*   **`main.py`**: The primary orchestrator script.

---

## 🚀 Setup & Execution

### 1. Prerequisites
*   **Python 3.10+**
*   **Docker Desktop** (Must be running for the Validator layer).
*   **Local LLM:** A Phi-3 GGUF model must be in the `models/` directory for on-prem execution.

### 2. Installation
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Environment Configuration (`.env`)
```bash
GITHUB_TOKEN=your_token
GITHUB_REPOSITORY=user/repo
OPENCLAW_API_KEY=your_key
SLACK_BOT_TOKEN=...
```

### 4. Running the Agent
*   **Immediate Run:** `python main.py .`
*   **Start Night Shift (2 AM):** `python scheduler.py`
*   **Test Scheduler:** `python scheduler.py test` (runs in 5 seconds).

---

## 🛠️ Current Status: FULLY OPERATIONAL

As of **May 7, 2026**, the project has completed all core development phases:
- ✅ **OpenClaw Integration:** Manifest and Heartbeat SDK fully integrated.
- ✅ **Autonomous Patching:** LLM now performs real file modifications, not mock data.
- ✅ **Self-Correction:** Agent can "heal" its own code by reading test failure logs.
- ✅ **Performance Optimized:** Docker builds reduced from 10 minutes to 45 seconds using custom snapshots.

---

## 🗺️ Roadmap: Future Updates
1.  **Multi-Language Support:** Expand detection and validation to Node.js, Go, and Java.
2.  **Jira Integration:** Automatically link PRs to corresponding tech debt tickets.
3.  **Code Review Summaries:** Use the LLM to write detailed code review comments for the generated PRs.

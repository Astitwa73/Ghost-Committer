import os
import logging
import requests

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        self.base_url = "https://api.telegram.org/bot"

        if not self.bot_token or not self.chat_id:
            logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found. Telegram notifications will be skipped.")

    def send_morning_digest(self, pr_url, stats, plan_summary, retries_used=0):
        """Send morning digest via Telegram."""
        if not self.bot_token or not self.chat_id:
            print("[Delivery] Skipping Telegram notification (missing credentials).")
            return {"status": "dry_run", "message": "Missing Telegram credentials"}

        branch = stats.get("branch", "chore/ghost-auto-[date]")
        lint_issues = stats.get("lint_issues", 0)

        message = (
            "Ghost Committer - Morning Report\n\n"
            f"Lint issues fixed: {lint_issues}\n"
            f"Retries used: {retries_used}/3\n"
            f"Branch: {branch}\n"
            f"PR: {pr_url or 'No PR (dry run)'}\n\n"
            "Fix Plan Summary:\n"
            f"{plan_summary[:300]}\n\n"
            "Tests passed. Review when you wake up!"
        )

        url = f"{self.base_url}{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            print("[Delivery] Telegram morning digest sent successfully.")
            return {"status": "success", "message": "Telegram notification sent"}
        except requests.RequestException as e:
            logger.error(f"[Delivery] Failed to send Telegram message: {e}")
            print(f"[Delivery] Failed to send Telegram message: {e}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    notifier = TelegramNotifier()
    result = notifier.send_morning_digest(
        pr_url="https://github.com/mock/repo/pull/42",
        stats={"lint_issues": 5, "branch": "chore/ghost-auto-20260502"},
        plan_summary="1. Fix lint issues.\n2. Remove dead code.\n3. Update dependencies.",
        retries_used=0
    )
    print(result)

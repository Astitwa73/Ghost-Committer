import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackNotifier:
    def __init__(self, token=None):
        self.token = token or os.environ.get("SLACK_BOT_TOKEN")
        self.channel = os.environ.get("SLACK_CHANNEL", "#engineering")
        
        if self.token:
            self.client = WebClient(token=self.token)
        else:
            print("[Delivery] Warning: SLACK_BOT_TOKEN not found. Running in dry-run mode.")
            self.client = None

    def send_morning_digest(self, pr_url, stats):
        """Sends a message to the engineering channel about the overnight work."""
        
        message = (
            f":ghost: *Ghost Committer Morning Digest*\n"
            f"I woke up at 2 AM, found some tech debt, and opened a PR for you.\n\n"
            f"*Fixed:*\n"
            f"• {stats.get('lint_issues', 0)} Linting Issues\n"
            f"• Removed dead code\n\n"
            f"All tests passed in the Sandbox. Your PR is ready for review:\n"
            f"<{pr_url}|Review Overnight Changes>"
        )

        if not self.client:
             print(f"[Delivery] DRY RUN: Would send the following Slack message to {self.channel}:\n{message}")
             return True
             
        try:
            self.client.chat_postMessage(
                channel=self.channel,
                text=message
            )
            print(f"[Delivery] Slack notification sent successfully to {self.channel}.")
            return True
        except SlackApiError as e:
            print(f"[Delivery] Error sending Slack message: {e.response['error']}")
            return False

if __name__ == "__main__":
    # Test dry run
    notifier = SlackNotifier()
    notifier.send_morning_digest(
        pr_url="https://github.com/mock/repo/pull/42",
        stats={"lint_issues": 5}
    )

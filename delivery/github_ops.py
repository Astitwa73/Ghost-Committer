import os
from github import Github, GithubException

class GitHubDelivery:
    def __init__(self, token=None, repo_name=None):
        # Fallback to environment variables if not passed directly
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.repo_name = repo_name or os.environ.get("GITHUB_REPOSITORY")
        
        if self.token:
            self.g = Github(self.token)
        else:
            print("[Delivery] Warning: GITHUB_TOKEN not found. Running in dry-run mode.")
            self.g = None

    def create_pull_request(self, branch_name, title, body, base_branch="main"):
        """Opens a Pull Request for the given branch."""
        print(f"[Delivery] Attempting to open PR for {branch_name} into {base_branch}...")
        
        if not self.g or not self.repo_name:
            print(f"[Delivery] DRY RUN: Would open PR '{title}' from {branch_name} to {base_branch}.")
            return {"status": "dry_run", "url": "http://github.com/mock/pr/1"}
            
        try:
            repo = self.g.get_repo(self.repo_name)
            
            # In a real scenario, you must 'git push' the branch to remote before this step.
            # The GitPatcher would handle the `git push origin <branch>`.
            
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch
            )
            print(f"[Delivery] Success! PR Created: {pr.html_url}")
            return {"status": "success", "url": pr.html_url}
            
        except GithubException as e:
            print(f"[Delivery] GitHub API Error: {e.data.get('message', str(e))}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            print(f"[Delivery] Unexpected error creating PR: {e}")
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Test dry run
    delivery = GitHubDelivery()
    delivery.create_pull_request(
        branch_name="chore/ghost-test", 
        title="Chore: Overnight Tech Debt Cleanup", 
        body="Fixed 5 linting issues."
    )

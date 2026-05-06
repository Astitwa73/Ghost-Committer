import datetime
import re
from urllib.parse import quote, urlparse


class GitPatcher:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        try:
            from git import Repo

            self.repo = Repo(repo_path)
            self.git = self.repo.git
            self.start_branch = self._current_branch()
        except Exception as e:
            print(f"[Patcher] Error initializing git repository at {repo_path}: {e}")
            self.repo = None
            self.git = None
            self.start_branch = None

    def _current_branch(self):
        try:
            return self.repo.active_branch.name
        except Exception:
            return None

    def remote_repo_name(self, remote="origin"):
        """Return owner/repo parsed from the configured git remote URL."""
        if not self.repo:
            return None

        try:
            remote_url = self.git.remote("get-url", remote).strip()
        except Exception:
            return None

        if remote_url.startswith("git@"):
            match = re.match(r"git@[^:]+:(?P<repo>.+?)(?:\.git)?$", remote_url)
            return match.group("repo") if match else None

        parsed = urlparse(remote_url)
        repo = parsed.path.strip("/")
        return repo.removesuffix(".git") if repo else None

    def create_branch(self, prefix="chore/ghost"):
        """Create and check out a unique branch for automated fixes."""
        if not self.repo:
            return None

        date_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"{prefix}-{date_str}"
        existing_branches = {head.name for head in self.repo.heads}
        suffix = 1
        while branch_name in existing_branches:
            branch_name = f"{prefix}-{date_str}-{suffix}"
            suffix += 1

        try:
            print(f"[Patcher] Creating and switching to branch: {branch_name}")
            self.git.checkout("-b", branch_name)
            return branch_name
        except Exception as e:
            print(f"[Patcher] Git error creating branch: {e}")
            return None

    def commit_changes(self, message):
        """Stage all changes and commit them."""
        if not self.repo:
            return False

        try:
            if not self.repo.is_dirty(untracked_files=True):
                print("[Patcher] No changes detected to commit.")
                return False

            print("[Patcher] Staging changes...")
            self.git.add(A=True)

            print(f"[Patcher] Committing with message: '{message}'")
            self.repo.index.commit(message)
            return True
        except Exception as e:
            print(f"[Patcher] Git error during commit: {e}")
            return False

    def push_branch(self, branch_name, remote="origin", repo_name=None, token=None):
        """Push the generated branch so GitHub can open a pull request."""
        if not self.repo:
            return {"status": "error", "message": "Git repository was not initialized."}

        try:
            print(f"[Patcher] Pushing branch: {branch_name}")
            if token and repo_name:
                owner_repo = repo_name.strip().removesuffix(".git")
                safe_token = quote(token, safe="")
                push_url = f"https://x-access-token:{safe_token}@github.com/{owner_repo}.git"
                self.git.push(push_url, f"{branch_name}:{branch_name}")
            else:
                self.git.push("-u", remote, branch_name)
            return {"status": "success"}
        except Exception as e:
            message = str(e)
            if token:
                message = message.replace(token, "<redacted>")
                message = message.replace(quote(token, safe=""), "<redacted>")
            print(f"[Patcher] Git error during push: {message}")
            return {"status": "error", "message": message}


if __name__ == "__main__":
    patcher = GitPatcher(".")
    if patcher.repo:
        branch = patcher.create_branch("test/ghost")
        if branch:
            with open("test_patch.txt", "w", encoding="utf-8") as f:
                f.write("Ghost committer was here.\n")

            success = patcher.commit_changes("chore: test ghost committer patcher")
            if success:
                print(f"Successfully committed to {branch}.")

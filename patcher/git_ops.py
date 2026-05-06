import os
import datetime
from git import Repo, GitCommandError

class GitPatcher:
    def __init__(self, repo_path):
        self.repo_path = repo_path
        try:
            self.repo = Repo(repo_path)
            self.git = self.repo.git
        except Exception as e:
            print(f"[Patcher] Error initializing git repository at {repo_path}: {e}")
            self.repo = None

    def create_branch(self, prefix="chore/ghost"):
        """Creates and checkouts a new branch for the automated fixes."""
        if not self.repo:
            return None

        date_str = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        branch_name = f"{prefix}-{date_str}"
        
        try:
            print(f"[Patcher] Creating and switching to branch: {branch_name}")
            new_branch = self.repo.create_head(branch_name)
            new_branch.checkout()
            return branch_name
        except GitCommandError as e:
            print(f"[Patcher] Git error creating branch: {e}")
            return None

    def commit_changes(self, message):
        """Stages all changes and commits them."""
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
        except GitCommandError as e:
            print(f"[Patcher] Git error during commit: {e}")
            return False

    def push_branch(self, branch_name):
        """Pushes the branch to origin so GitHub can create a PR against it."""
        if not self.repo:
            return False
        try:
            print(f"[Patcher] Pushing branch {branch_name} to origin...")
            self.git.push("origin", branch_name)
            print(f"[Patcher] Branch {branch_name} pushed successfully.")
            return True
        except GitCommandError as e:
            print(f"[Patcher] Git push failed: {e}")
            return False

    def get_github_repo_name(self):
        """Returns 'owner/repo' from the origin remote URL, or None if not a GitHub remote."""
        if not self.repo:
            return None
        try:
            url = self.repo.remotes.origin.url
            # handles both https://github.com/owner/repo.git and git@github.com:owner/repo.git
            if "github.com" not in url:
                return None
            url = url.rstrip("/").removesuffix(".git")
            if url.startswith("git@"):
                return url.split("github.com:")[-1]
            return url.split("github.com/")[-1]
        except Exception:
            return None

if __name__ == "__main__":
    # Test script assumes it's run inside a git repository
    patcher = GitPatcher(".")
    if patcher.repo:
        branch = patcher.create_branch("test/ghost")
        if branch:
            # Mock a file change
            with open("test_patch.txt", "w") as f:
                f.write("Ghost committer was here.\n")
            
            success = patcher.commit_changes("chore: test ghost committer patcher")
            if success:
                print(f"Successfully committed to {branch}.")

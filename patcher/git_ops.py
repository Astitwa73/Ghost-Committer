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
        try:
            self.repo.remotes.origin.push(branch_name)
            print(f"[Patcher] Branch {branch_name} pushed to GitHub.")
            return True
        except Exception as e:
            print(f"[Patcher] Push failed: {e}")
            return False

    def cleanup_branch(self, branch_name):
        try:
            self.repo.heads.main.checkout()
            self.repo.delete_head(branch_name, force=True)
            print(f"[Patcher] Branch {branch_name} deleted.")
        except Exception as e:
            print(f"[Patcher] Cleanup failed: {e}")

if __name__ == "__main__":
    patcher = GitPatcher(".")
    if patcher.repo:
        branch = patcher.create_branch("test/ghost")
        if branch:
            with open("test_patch.txt", "w") as f:
                f.write("Ghost committer was here.\n")
            success = patcher.commit_changes("chore: test ghost committer patcher")
            if success:
                print(f"Successfully committed to {branch}.")
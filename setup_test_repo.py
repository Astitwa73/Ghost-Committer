import os
from github import Github
from dotenv import load_dotenv

load_dotenv()

def setup_test_repo():
    """Create a private GitHub test repository and seed it with sample tech debt files."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not found in .env")
        return

    g = Github(token)
    user = g.get_user()
    repo_name = "ghost-test-bench"

    try:
        # Create the repository
        print(f"Creating repository '{repo_name}'...")
        repo = user.create_repo(repo_name, private=True, description="Testing ground for Ghost Committer agent.")
        print(f"Successfully created: {repo.html_url}")

        # Add tech debt sample file
        content = """# Tech Debt Sample File

def complex_math(a, b, c):
    \"\"\"Calculate a complex mathematical result based on inputs a, b, and c.\"\"\"
    # This is a messy function with no docstring
    if a > 0:
        if b > 0:
            if c > 0:
                result = (a + b) * c
                if result > 100:
                    return result / 2
                else:
                    return result
            else:
                return a - b
        else:
            return a * b
    return 0

# TODO: Refactor this function to be simpler
def legacy_helper(x):
    \"\"\"Increment the input value by one.\"\"\"
    return x + 1

def function_with_no_docstring():
    \"\"\"Return True.\"\"\"
    return True
"""
        repo.create_file("debt_sample.py", "initial commit with tech debt", content)
        print("Added 'debt_sample.py' with tech debt.")
        
        # Add a dummy test file
        test_content = """import unittest
from debt_sample import complex_math

class TestDebt(unittest.TestCase):
    def test_complex_math(self):
        self.assertEqual(complex_math(1, 2, 3), 9)

if __name__ == '__main__':
    unittest.main()
"""
        repo.create_file("test_debt.py", "add tests", test_content)
        print("Added 'test_debt.py'.")
        
        print("\n✅ Test repository is ready at:", repo.html_url)
        print(f"Update your .env GITHUB_REPOSITORY to: {user.login}/{repo_name}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    setup_test_repo()
"""Phase 3: Deploy to GitHub Pages via git + gh CLI."""

import subprocess
from pathlib import Path


class GitHubDeployer:
    """Initialize git, create GitHub repo, push, and enable Pages."""

    def __init__(self, repo_root: Path):
        self.root = repo_root

    def deploy(self, dry_run: bool = False) -> bool:
        """Full deploy pipeline: git init → repo create → push → enable Pages."""
        # Pre-flight checks
        if not self._check_tool("git --version", "git"):
            return False
        if not self._check_tool("gh --version", "gh CLI"):
            return False
        if not self._check_tool("gh auth status", "gh auth"):
            return False

        dist_file = self.root / "dist" / "index.html"
        if not dist_file.exists():
            print("  dist/index.html not found. Run 'build' first.")
            return False

        if dry_run:
            print("  DRY RUN — would perform:")
            print("    1. git init (if needed)")
            print("    2. gh repo create (if needed)")
            print("    3. git add + commit + push")
            print("    4. Enable GitHub Pages")
            return True

        # Step 1: git init
        git_dir = self.root / ".git"
        if not git_dir.exists():
            print("  Initializing git repository...")
            if not self._run("git init"):
                return False
            # Ensure main branch
            self._run("git branch -M main")

        # Step 2: Stage and commit
        print("  Staging files...")
        files_to_add = [
            "dist/", "templates/", "src/", "config.yaml",
            "run_pipeline.py", ".gitignore"
        ]
        for f in files_to_add:
            path = self.root / f.rstrip("/")
            if path.exists():
                self._run(f"git add {f}")

        # Check if there are changes to commit
        result = subprocess.run(
            "git diff --cached --quiet",
            shell=True, cwd=self.root
        )
        if result.returncode == 0:
            print("  No changes to commit.")
        else:
            print("  Committing...")
            if not self._run('git commit -m "Update course content"'):
                return False

        # Step 3: Check/create remote
        has_remote = self._run_quiet("git remote get-url origin")

        if not has_remote:
            repo_name = self.root.name
            print(f"  Creating GitHub repo: {repo_name}...")
            if not self._run(f"gh repo create {repo_name} --public --source=. --push"):
                return False
        else:
            print("  Pushing to existing remote...")
            if not self._run("git push origin main"):
                # Try setting upstream
                self._run("git push -u origin main")

        # Step 4: Enable GitHub Pages
        owner = self._get_output("gh api user --jq .login")
        if owner:
            repo_name = self.root.name
            full_name = f"{owner}/{repo_name}"
            print(f"  Enabling GitHub Pages for {full_name}...")

            # Try to enable pages — may already be enabled
            self._run(
                f'gh api repos/{full_name}/pages -X POST '
                f'-f build_type=legacy '
                f"-f source[branch]=main "
                f"-f source[path]=/dist",
                silent=True
            )

            url = f"https://{owner}.github.io/{repo_name}/dist/"
            print(f"\n  Live URL: {url}")
        else:
            print("  Could not determine GitHub username")

        return True

    def _run(self, cmd: str, silent: bool = False) -> bool:
        """Run a shell command and return success."""
        result = subprocess.run(
            cmd, shell=True, cwd=self.root,
            capture_output=True, text=True
        )
        if result.returncode != 0 and not silent:
            stderr = result.stderr.strip()
            if stderr:
                print(f"    Error: {stderr[:200]}")
        return result.returncode == 0

    def _run_quiet(self, cmd: str) -> bool:
        """Run command silently, return success."""
        result = subprocess.run(
            cmd, shell=True, cwd=self.root,
            capture_output=True, text=True
        )
        return result.returncode == 0

    def _get_output(self, cmd: str) -> str | None:
        """Run command and return stdout."""
        result = subprocess.run(
            cmd, shell=True, cwd=self.root,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def _check_tool(self, cmd: str, name: str) -> bool:
        """Check if a CLI tool is available."""
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  {name} not available. Install it first.")
            return False
        return True

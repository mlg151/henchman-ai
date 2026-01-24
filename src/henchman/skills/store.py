import subprocess
from pathlib import Path

import yaml

from .models import Skill


class SkillStore:
    """Storage for skills with git-backed versioning."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Initialize SkillStore.

        Args:
            skills_dir: Directory to store skills. Defaults to ~/.henchman/skills.
        """
        if skills_dir:
            self.skills_dir = skills_dir
        else:
            self.skills_dir = Path.home() / ".henchman" / "skills"

        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensure directory and git repo exist."""
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        if not (self.skills_dir / ".git").exists():
            self._run_git(["init"])
            # Set local config for this repo to avoid "Please tell me who you are" errors
            self._run_git(["config", "user.email", "henchman@local"])
            self._run_git(["config", "user.name", "Henchman CLI"])

    def _run_git(self, args: list[str]) -> None:
        """Run a git command in the skills directory."""
        subprocess.run(
            ["git", *args], cwd=self.skills_dir, check=True, capture_output=True
        )

    def save(self, skill: Skill, message: str | None = None) -> None:
        """Save skill to YAML and commit.

        Args:
            skill: Skill to save.
            message: Optional commit message.
        """
        file_path = self.skills_dir / f"{skill.name}.yaml"

        # Serialize to dict with JSON-compatible types (handling datetimes)
        data = skill.model_dump(mode="json")

        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False)

        self._run_git(["add", file_path.name])
        msg = message or f"Update skill: {skill.name}"
        self._run_git(["commit", "-m", msg])

    def load(self, name: str) -> Skill:
        """Load skill by name.

        Args:
            name: Skill name.

        Returns:
            The loaded Skill.
        """
        file_path = self.skills_dir / f"{name}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Skill not found: {name}")

        with open(file_path) as f:
            data = yaml.safe_load(f)

        return Skill(**data)

    def list_skills(self) -> list[Skill]:
        """List all available skills.

        Returns:
            List of Skills.
        """
        skills = []
        for file_path in self.skills_dir.glob("*.yaml"):
            try:
                with open(file_path) as f:
                    data = yaml.safe_load(f)
                    skills.append(Skill(**data))
            except Exception:
                continue  # Skip malformed files
        return skills

    def delete(self, name: str) -> None:
        """Delete a skill and commit.

        Args:
            name: Name of skill to delete.
        """
        file_path = self.skills_dir / f"{name}.yaml"
        if file_path.exists():
            file_path.unlink()
            self._run_git(["add", file_path.name])
            self._run_git(["commit", "-m", f"Delete skill: {name}"])

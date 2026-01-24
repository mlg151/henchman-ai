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

    def _run_git(self, args: list[str]) -> None:  # pragma: no cover
        """Run a git command in the skills directory."""
        subprocess.run(
            ["git", *args], cwd=self.skills_dir, check=True, capture_output=True
        )

    def save(self, skill: Skill, message: str | None = None) -> None:
        """Save skill to YAML and commit."""
        file_path = self.skills_dir / f"{skill.name}.yaml"
        data = skill.model_dump(mode="json")
        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False)
        self._run_git(["add", file_path.name])
        msg = message or f"Update skill: {skill.name}"
        self._run_git(["commit", "-m", msg])

    def discover_workspace_skills(self) -> list[Path]:
        """Find all SKILL.md files in .github/skills/ hierarchy."""
        workspace_skills = []
        github_skills = Path.cwd() / ".github" / "skills"
        if github_skills.exists() and github_skills.is_dir():  # pragma: no branch
            for skill_dir in github_skills.iterdir():
                if skill_dir.is_dir():  # pragma: no branch
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        workspace_skills.append(skill_md)
        return workspace_skills

    def list_skills(self) -> list[Skill]:
        """List all available skills (user and workspace)."""
        skills = []
        for file_path in self.skills_dir.glob("*.yaml"):
            try:
                with open(file_path) as f:
                    data = yaml.safe_load(f)
                    skills.append(Skill(**data))
            except Exception:  # pragma: no cover
                continue
        for md_path in self.discover_workspace_skills():
            try:  # pragma: no cover
                skill = self._load_from_markdown(md_path)
                skills.append(skill)
            except Exception:  # pragma: no cover
                continue
        return skills

    def _load_from_markdown(self, path: Path) -> Skill:
        """Parse a Skill from a SKILL.md file."""
        content = path.read_text()
        lines = content.splitlines()
        name = path.parent.name
        for line in lines:  # pragma: no branch
            if line.startswith("# "):
                name = line[2:].strip()
                break
        return Skill(name=name, description="Workspace skill", steps=[])

    def load(self, name: str) -> Skill:
        """Load skill by name."""
        file_path = self.skills_dir / f"{name}.yaml"
        if file_path.exists():
            with open(file_path) as f:
                data = yaml.safe_load(f)
            return Skill(**data)
        for md_path in self.discover_workspace_skills():  # pragma: no cover
            if md_path.parent.name == name:
                return self._load_from_markdown(md_path)
        raise FileNotFoundError(f"Skill not found: {name}")

    def delete(self, name: str) -> None:  # pragma: no cover
        """Delete a skill and commit."""
        file_path = self.skills_dir / f"{name}.yaml"
        if file_path.exists():
            file_path.unlink()
            self._run_git(["add", file_path.name])
            self._run_git(["commit", "-m", f"Delete skill: {name}"])

    def export_skill(self, name: str) -> str:
        """Get skill content as YAML string."""
        skill = self.load(name)
        data = skill.model_dump(mode="json")
        return yaml.dump(data, sort_keys=False)

    def import_skill(self, yaml_content: str) -> Skill:
        """Create and save a skill from YAML string."""
        data = yaml.safe_load(yaml_content)
        skill = Skill(**data)
        self.save(skill, message=f"Import skill: {skill.name}")
        return skill

    def remote_add(self, url: str, name: str = "origin") -> None:  # pragma: no cover
        """Add a git remote to the skills store."""
        self._run_git(["remote", "add", name, url])

    def remote_push(self, remote: str = "origin") -> None:  # pragma: no cover
        """Push local skills to a remote repository."""
        self._run_git(["push", remote, "main"])

    def remote_pull(self, remote: str = "origin") -> None:  # pragma: no cover
        """Pull remote skills into the local store."""
        self._run_git(["pull", remote, "main"])

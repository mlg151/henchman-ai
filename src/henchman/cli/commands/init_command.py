"""Guided project bootstrap for Tier 1 local settings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import click

from henchman.config.paths import resolve_project_settings_path
from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.schema import UI_OUTPUT_STYLES, UI_THEME_NAMES

_ABORT_ACTION: Final[str] = "abort"
_EXIT_ACTION: Final[str] = "exit"
_DEFAULT_ABORT_CHORD: Final[str] = "c-c"
_DEFAULT_EXIT_CHORD: Final[str] = "c-d"
_DEFAULT_OUTPUT_STYLE: Final[str] = "verbose"
_DEFAULT_THEME: Final[str] = "dark"


@dataclass(frozen=True, slots=True)
class _InitAnswers:
    """Collected answers for the guided init flow."""

    show_line_numbers: bool
    output_style: str
    theme: str
    abort_chord: str
    exit_chord: str


def create_init_command(*, project_root: Path | None = None) -> click.Command:
    """Create the guided ``henchman init`` command.

    Args:
        project_root: Optional project root used for deterministic tests and
            project-local settings writes.

    Returns:
        A click command that bootstraps project-local Tier 1 settings.
    """

    @click.command(
        name="init",
        help="Interactively bootstrap project-local Tier 1 settings.",
    )
    def init_command() -> None:
        repository = SettingsRepository(project_root=project_root)
        existing_project_settings = repository.view(scope=SettingsScope.PROJECT)
        if existing_project_settings:
            click.echo("Detected existing project-local settings.")
            if not click.confirm("Update guided bootstrap values?", default=False):
                click.echo("Init cancelled; existing settings were preserved.")
                return

        answers = _prompt_for_answers(repository)
        repository.sync_ui_settings(
            output_style=answers.output_style,
            theme=answers.theme,
            keybindings=_build_keybindings(answers),
            scope=SettingsScope.PROJECT,
        )
        repository.set(
            "ui.show_line_numbers",
            answers.show_line_numbers,
            scope=SettingsScope.PROJECT,
        )

        settings_dir = resolve_project_settings_path(project_root)
        settings_dir.mkdir(parents=True, exist_ok=True)
        action = "Updated" if existing_project_settings else "Created"
        click.echo(f"{action} project settings in {settings_dir}")
        click.echo("Next: run `henchman help` to explore Tier 1 commands.")

    return init_command


def _prompt_for_answers(repository: SettingsRepository) -> _InitAnswers:
    """Prompt for the focused Tier 1 bootstrap choices."""
    project_view = repository.view(scope=SettingsScope.PROJECT)
    project_ui = project_view.get("ui")
    persisted_ui = project_ui if isinstance(project_ui, dict) else {}
    keybindings_value = persisted_ui.get("keybindings")
    existing_keybindings = keybindings_value if isinstance(keybindings_value, dict) else {}

    click.echo("Configure project-local workspace defaults.")

    return _InitAnswers(
        show_line_numbers=click.confirm(
            "Show line numbers in file output?",
            default=_existing_bool(
                persisted_ui.get("show_line_numbers"),
                fallback=True,
            ),
        ),
        output_style=click.prompt(
            "Preferred output style",
            type=click.Choice(UI_OUTPUT_STYLES, case_sensitive=False),
            default=_existing_choice(
                persisted_ui.get("output_style"),
                choices=UI_OUTPUT_STYLES,
                fallback=_DEFAULT_OUTPUT_STYLE,
            ),
            show_choices=True,
        ),
        theme=click.prompt(
            "Preferred theme",
            type=click.Choice(UI_THEME_NAMES, case_sensitive=False),
            default=_existing_choice(
                persisted_ui.get("theme"),
                choices=UI_THEME_NAMES,
                fallback=_DEFAULT_THEME,
            ),
            show_choices=True,
        ),
        abort_chord=click.prompt(
            "Keybinding for abort",
            default=_key_for_action(existing_keybindings, _ABORT_ACTION, _DEFAULT_ABORT_CHORD),
        ).strip(),
        exit_chord=click.prompt(
            "Keybinding for exit",
            default=_key_for_action(existing_keybindings, _EXIT_ACTION, _DEFAULT_EXIT_CHORD),
        ).strip(),
    )


def _build_keybindings(answers: _InitAnswers) -> dict[str, str]:
    """Build a validated keybinding mapping from prompt answers."""
    if not answers.abort_chord:
        msg = "Abort keybinding must not be blank."
        raise click.ClickException(msg)
    if not answers.exit_chord:
        msg = "Exit keybinding must not be blank."
        raise click.ClickException(msg)
    if answers.abort_chord == answers.exit_chord:
        msg = "Abort and exit keybindings must differ."
        raise click.ClickException(msg)
    return {
        answers.abort_chord: _ABORT_ACTION,
        answers.exit_chord: _EXIT_ACTION,
    }


def _existing_bool(value: object, *, fallback: bool) -> bool:
    """Return an existing boolean value when present, otherwise a fallback."""
    return value if isinstance(value, bool) else fallback


def _existing_choice(value: object, *, choices: Sequence[str], fallback: str) -> str:
    """Return an existing choice when valid, otherwise a fallback."""
    if isinstance(value, str) and value in choices:
        return value
    return fallback


def _key_for_action(keybindings: dict[object, object], action: str, fallback: str) -> str:
    """Find the first chord mapped to an action, or return a fallback."""
    for chord, bound_action in keybindings.items():
        if isinstance(chord, str) and bound_action == action:
            return chord
    return fallback


__all__ = ["create_init_command", "register_init_command"]


def register_init_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Command:
    """Register the init command on a root click group.

    Args:
        cli: Root click group that should expose the init command.
        project_root: Optional project root for deterministic tests.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_init_command(project_root=project_root)
    cli.add_command(command)
    return command

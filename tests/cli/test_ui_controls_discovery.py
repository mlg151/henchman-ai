"""Terminal UI controls stay TUI-scoped in the shared discovery truth.

Issue #14 requires discovery/help/doctor to derive from the shared
capability matrix and to never advertise TUI-only controls as generic
commands. The six typed ``ui.*`` settings therefore need a runtime-truth
entry that classifies them as TUI-scoped rather than tool-backed surfaces.
"""

from henchman.cli.commands.discovery_capabilities import (
    build_discovery_capabilities,
)

UI_CONTROL_NAMES = (
    "ui.output_mode",
    "ui.reduced_motion",
    "ui.detail_density",
    "ui.keyboard_mode",
    "ui.mouse_capture",
    "ui.layout.compact_tables",
)


def _ui_controls_capability() -> object:
    capabilities = build_discovery_capabilities()
    return next(item for item in capabilities if item.name == "terminal UI controls")


def test_ui_controls_are_classified_undiscoverable():
    capability = _ui_controls_capability()
    assert capability.classification == "undiscoverable"


def test_ui_controls_summary_does_not_advertise_generic_commands():
    capability = _ui_controls_capability()
    assert "generic commands" in capability.summary.casefold()


def test_ui_controls_detail_covers_config_ownership_and_consumers():
    capability = _ui_controls_capability()
    detail = capability.detail.casefold()
    assert "config" in detail
    for name in UI_CONTROL_NAMES:
        assert name.casefold() in detail


def test_ui_controls_are_searchable_by_their_setting_names():
    capability = _ui_controls_capability()
    for name in UI_CONTROL_NAMES:
        assert name.casefold() in capability.search_text


def test_ui_controls_classification_is_stable_across_runtime_toolsets():
    for registered in ((), ("shell", "task_get")):
        capabilities = build_discovery_capabilities(registered_tool_names=registered)
        capability = next(item for item in capabilities if item.name == "terminal UI controls")
        assert capability.classification == "undiscoverable"

"""Tests for Tier 10 Textual UI enhancements."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.widgets import Input, Label, Select, TabbedContent

from henchman.advanced import TaskService
from henchman.cli.textual_app import HenchmanTextualApp, TextualConfig
from henchman.cli.textual_screens import (
    AutoModeScreen,
    BridgeScreen,
    ConfirmToolScreen,
    ExportScreen,
    FeedbackScreen,
    HistorySearchScreen,
    McpServersScreen,
    ModelPickerScreen,
    OnboardingScreen,
    SearchScreen,
    ThemePickerScreen,
)
from henchman.cli.textual_widgets import (
    AgentSummaryPanel,
    MemoryIndicator,
    SettingsPanel,
    SkillPanel,
    TaskListWidget,
    TeamPanel,
)
from henchman.config.schema import Settings
from henchman.core.session_data import Session
from henchman.core.session_models import SessionMessage
from henchman.team import BridgeSessionService, TeamWorkspaceService
from henchman.tools.base import ConfirmationRequest


class TestTier10Widgets:
    """Test workspace widgets used by the Tier 10 TUI."""

    def test_agent_summary_panel_renders_provider_and_mode(self) -> None:
        panel = AgentSummaryPanel()

        panel.update_summary(
            provider_name="deepseek",
            model_name="deepseek-chat",
            mode="Plan",
            active_agent="tech_lead",
            tools=14,
        )

        rendered = panel.render()
        assert "deepseek:deepseek-chat" in rendered
        assert "Plan" in rendered
        assert "tech_lead" in rendered
        assert "14" in rendered

    def test_memory_indicator_renders_counts(self) -> None:
        indicator = MemoryIndicator()

        indicator.update_counts(session_messages=8, history_entries=5, context_loaded=True)

        rendered = indicator.render()
        assert "8" in rendered
        assert "5" in rendered
        assert "loaded" in rendered.lower()

    def test_task_skill_team_and_settings_widgets_render_lists(self) -> None:
        task_widget = TaskListWidget()
        skill_widget = SkillPanel()
        team_widget = TeamPanel()
        settings_widget = SettingsPanel()

        task_widget.set_tasks(["task-1 [running] lint", "task-2 [completed] tests"])
        skill_widget.set_skills(["qa", "design-review"])
        team_widget.set_workspaces(["core-team (2 members)"])
        settings_widget.update_settings(
            theme="dark",
            auto_mode=True,
            provider="deepseek",
            mcp_servers=3,
        )

        assert "task-1" in task_widget.render()
        assert "qa" in skill_widget.render()
        assert "core-team" in team_widget.render()
        rendered = settings_widget.render()
        assert "dark" in rendered
        assert "auto" in rendered.lower()
        assert "3" in rendered


class TestTier10Screens:
    """Test the Tier 10 modal dialogs."""

    def test_confirm_tool_screen_supports_permission_approval_shortcuts(self) -> None:
        screen = ConfirmToolScreen(
            ConfirmationRequest(
                tool_name="write_file",
                description="Write a file to disk",
                params={"path": "demo.txt"},
                risk_level="medium",
            ),
        )
        dismiss = MagicMock()
        screen.dismiss = dismiss

        screen.action_approve()
        screen.action_deny()

        dismiss.assert_any_call(result=True)
        dismiss.assert_any_call(result=False)

    def test_search_screen_buttons_dismiss_with_query_or_clear(self) -> None:
        screen = SearchScreen()
        dismiss = MagicMock()
        screen.dismiss = dismiss

        mock_input = MagicMock(spec=Input)
        mock_input.value = "provider"

        with patch.object(screen, "query_one", return_value=mock_input):
            search_event = MagicMock()
            search_event.button.id = "btn-search"
            screen.on_button_pressed(search_event)

            clear_event = MagicMock()
            clear_event.button.id = "btn-clear"
            screen.on_button_pressed(clear_event)

            cancel_event = MagicMock()
            cancel_event.button.id = "btn-cancel"
            screen.on_button_pressed(cancel_event)

        dismiss.assert_any_call("provider")
        dismiss.assert_any_call("")
        dismiss.assert_any_call(None)

    def test_history_search_screen_builds_recent_history_options(self) -> None:
        options = HistorySearchScreen._build_options(
            ["first prompt", "second prompt", "third prompt"],
        )

        assert options[0][1] == "third prompt"
        assert options[1][1] == "second prompt"
        assert options[2][1] == "first prompt"

    def test_theme_picker_screen_lists_dark_and_light(self) -> None:
        options = ThemePickerScreen._build_options()

        assert ("Dark", "dark") in options
        assert ("Light", "light") in options

    def test_model_picker_screen_lists_provider_models(self) -> None:
        settings = MagicMock()
        settings.providers.default = "deepseek"
        settings.providers.deepseek = {"model": "deepseek-chat"}
        settings.providers.anthropic = {"model": "claude-sonnet"}
        settings.providers.ollama = {}

        options = ModelPickerScreen._build_options(settings)

        assert ("deepseek (deepseek-chat)", "deepseek") in options
        assert ("anthropic (claude-sonnet)", "anthropic") in options
        assert all(value != "ollama" for _, value in options)

    def test_auto_mode_export_feedback_and_onboarding_screens_dismiss_values(self) -> None:
        auto_mode = AutoModeScreen()
        export = ExportScreen()
        feedback = FeedbackScreen()
        onboarding = OnboardingScreen()

        auto_mode.dismiss = MagicMock()
        export.dismiss = MagicMock()
        feedback.dismiss = MagicMock()
        onboarding.dismiss = MagicMock()

        auto_yes = MagicMock()
        auto_yes.button.id = "btn-enable"
        auto_mode.on_button_pressed(auto_yes)

        export_md = MagicMock()
        export_md.button.id = "btn-markdown"
        export.on_button_pressed(export_md)

        feedback_rating = MagicMock(spec=Select)
        feedback_rating.value = "love_it"
        with patch.object(feedback, "query_one", return_value=feedback_rating):
            feedback_submit = MagicMock()
            feedback_submit.button.id = "btn-submit"
            feedback.on_button_pressed(feedback_submit)

        onboarding_theme = MagicMock()
        onboarding_theme.button.id = "btn-theme"
        onboarding.on_button_pressed(onboarding_theme)

        auto_mode.dismiss.assert_called_once_with(True)
        export.dismiss.assert_called_once_with("markdown")
        feedback.dismiss.assert_called_once_with("love_it")
        onboarding.dismiss.assert_called_once_with("theme")

    def test_bridge_and_mcp_screens_build_entries(self) -> None:
        bridge_entries = BridgeScreen._build_entries(
            ["core-team / bridge-1 (connected)", "ops / bridge-2 (idle)"],
        )
        mcp_entries = McpServersScreen._build_entries(
            configured=["filesystem", "github"],
            connected=["filesystem"],
        )

        assert "bridge-1" in bridge_entries[0]
        assert "filesystem" in mcp_entries[0]
        assert "github" in mcp_entries[1]


class TestTier10AppWiring:
    """Test Tier 10 screen actions and workspace refresh wiring."""

    @pytest.fixture
    def textual_app(self) -> HenchmanTextualApp:
        provider = MagicMock()
        provider.name = "deepseek"
        provider.model = "deepseek-chat"

        settings = MagicMock()
        settings.ui.theme = "dark"
        settings.ui.keybindings = {}
        settings.plan_mode = False
        settings.mcp_servers = {"filesystem": MagicMock()}
        settings.providers.default = "deepseek"

        return HenchmanTextualApp(
            provider=provider,
            config=TextualConfig(),
            settings=settings,
            environment_context="Test context",
        )

    def test_tier10_actions_push_expected_screens(self, textual_app: HenchmanTextualApp) -> None:
        with patch.object(textual_app, "push_screen") as push_screen:
            textual_app.action_show_search_dialog()
            textual_app.action_show_history_search()
            textual_app.action_show_theme_picker()
            textual_app.action_show_model_picker()
            textual_app.action_show_auto_mode_dialog()
            textual_app.action_show_bridge_dialog()
            textual_app.action_show_export_dialog()
            textual_app.action_show_feedback_dialog()
            textual_app.action_show_mcp_servers()
            textual_app.action_show_onboarding()

        assert push_screen.call_count == 10

    @pytest.mark.anyio
    async def test_workspace_tab_mounts_and_renders_persisted_project_data(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The real app tree must expose persisted workspace services to users."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        task_service = TaskService(project_root=tmp_path)
        task = await task_service.start_task(
            argv=[sys.executable, "-c", "print('mounted')"],
            title="Mounted task",
        )
        await task_service.wait_for_task(task.task_id, timeout=10)
        skill_path = tmp_path / ".henchman" / "skills" / "mounted.yaml"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(
            "name: mounted-skill\ndescription: Mounted in the workspace\n",
            encoding="utf-8",
        )
        TeamWorkspaceService(project_root=tmp_path).create_workspace(
            name="mounted-team",
            members=["matt", "henchman"],
        )

        def initialize() -> None:
            context = MagicMock()
            context.session_manager.current = None
            context.mcp_manager = None
            context.background_tasks = []
            context.orchestrator.aclose = AsyncMock()
            textual_app.core_context = context
            textual_app.input_handler = None

        with (
            patch.object(textual_app, "_initialize_core_components", initialize),
            patch.object(textual_app, "_populate_context_tree"),
            patch.object(textual_app, "_show_welcome"),
            patch.object(textual_app, "_load_history"),
        ):
            async with textual_app.run_test(size=(120, 50)) as pilot:
                await pilot.pause()
                tabs = textual_app.query_one(TabbedContent)
                tabs.active = "tab-workspace"
                await pilot.pause()

                assert (
                    "Mounted task"
                    in textual_app.query_one(
                        "#task-list-widget",
                        TaskListWidget,
                    ).render()
                )
                assert (
                    "mounted-skill"
                    in textual_app.query_one(
                        "#skill-components",
                        SkillPanel,
                    ).render()
                )
                assert (
                    "mounted-team"
                    in textual_app.query_one(
                        "#team-components",
                        TeamPanel,
                    ).render()
                )

        textual_app.core_context.orchestrator.aclose.assert_awaited_once()

    @pytest.mark.anyio
    async def test_bridge_action_shows_persisted_entries(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Opening Bridges must show real bridge metadata in the modal."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        workspace = TeamWorkspaceService(project_root=tmp_path).create_workspace(
            name="pilot-team",
            members=["matt"],
        )
        BridgeSessionService(project_root=tmp_path).open_bridge(
            workspace_id=workspace.workspace_id,
            remote_session="remote-pilot-session",
            created_by="matt",
        )

        with (
            patch.object(textual_app, "_initialize_core_components"),
            patch.object(textual_app, "_populate_context_tree"),
            patch.object(textual_app, "_show_welcome"),
            patch.object(textual_app, "_load_history"),
        ):
            async with textual_app.run_test(size=(120, 50)) as pilot:
                textual_app.query_one(TabbedContent).active = "tab-workspace"
                await pilot.pause()
                await pilot.click("#workspace-bridges")
                await pilot.pause()

                entry_label = textual_app.screen.query_one("#bridge-entries", Label)
                assert "remote-pilot-session" in str(entry_label.render())

    @pytest.mark.anyio
    async def test_export_action_button_writes_the_active_session(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The mounted export button must deliver its result to the exporter."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        current_session = Session(
            id="pilot-export",
            project_hash="project-1",
            started="2026-09-03T10:00:00+00:00",
            last_updated="2026-09-03T10:01:00+00:00",
            messages=[SessionMessage(role="user", content="Export from the modal")],
        )

        def initialize() -> None:
            context = MagicMock()
            context.session_manager.current = current_session
            context.mcp_manager = None
            context.background_tasks = []
            context.orchestrator.aclose = AsyncMock()
            textual_app.core_context = context
            textual_app.input_handler = None

        with (
            patch.object(textual_app, "_initialize_core_components", initialize),
            patch.object(textual_app, "_populate_context_tree"),
            patch.object(textual_app, "_show_welcome"),
            patch.object(textual_app, "_load_history"),
        ):
            async with textual_app.run_test(size=(120, 50)) as pilot:
                textual_app.query_one(TabbedContent).active = "tab-workspace"
                await pilot.pause()
                await pilot.click("#workspace-export")
                await pilot.pause()
                await pilot.click("#btn-markdown")
                await pilot.pause()

        textual_app.core_context.orchestrator.aclose.assert_awaited_once()
        output = (tmp_path / "session_pilot-export.md").read_text(encoding="utf-8")
        assert "Export from the modal" in output

    @pytest.mark.anyio
    async def test_onboarding_settings_opens_the_mounted_workspace(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The onboarding result callback must target a real tab."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        with (
            patch.object(textual_app, "_initialize_core_components"),
            patch.object(textual_app, "_populate_context_tree"),
            patch.object(textual_app, "_show_welcome"),
            patch.object(textual_app, "_load_history"),
        ):
            async with textual_app.run_test(size=(120, 50)) as pilot:
                textual_app.action_show_onboarding()
                await pilot.pause()
                await pilot.click("#btn-settings")
                await pilot.pause()

                assert textual_app.query_one(TabbedContent).active == "tab-workspace"

    @pytest.mark.anyio
    async def test_onboarding_theme_routes_to_theme_picker_action(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Choosing Theme in onboarding must continue into the theme picker."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        with (
            patch.object(textual_app, "_initialize_core_components"),
            patch.object(textual_app, "_populate_context_tree"),
            patch.object(textual_app, "_show_welcome"),
            patch.object(textual_app, "_load_history"),
            patch.object(textual_app, "action_show_theme_picker") as show_theme,
        ):
            async with textual_app.run_test(size=(120, 50)) as pilot:
                textual_app.action_show_onboarding()
                await pilot.pause()
                await pilot.click("#btn-theme")
                await pilot.pause()

        show_theme.assert_called_once_with()

    def test_bridge_action_reports_persistence_errors(
        self,
        textual_app: HenchmanTextualApp,
    ) -> None:
        """Bridge persistence failures must be surfaced instead of opening empty UI."""

        with (
            patch.object(textual_app, "notify") as notify,
            patch.object(textual_app, "push_screen") as push_screen,
            patch(
                "henchman.cli.textual_mixins.TeamWorkspaceService.list_workspaces",
                side_effect=OSError("workspace store unreadable"),
            ),
        ):
            textual_app.action_show_bridge_dialog()

        push_screen.assert_not_called()
        assert "Failed to load bridges" in notify.call_args.args[0]
        assert notify.call_args.kwargs["severity"] == "error"

    def test_refresh_workspace_widgets_populates_all_tier10_panels(
        self,
        textual_app: HenchmanTextualApp,
    ) -> None:
        session_manager = MagicMock()
        session_manager.current = MagicMock(messages=[1, 2, 3, 4])
        mcp_manager = MagicMock()
        mcp_manager.clients = {"filesystem": MagicMock(), "github": MagicMock()}
        textual_app.core_context = MagicMock(
            session_manager=session_manager,
            mcp_manager=mcp_manager,
        )
        textual_app.command_history = ["one", "two"]

        summary = MagicMock(spec=AgentSummaryPanel)
        memory = MagicMock(spec=MemoryIndicator)
        tasks = MagicMock(spec=TaskListWidget)
        skills = MagicMock(spec=SkillPanel)
        team = MagicMock(spec=TeamPanel)
        settings_panel = MagicMock(spec=SettingsPanel)

        def query_one(selector: str, *_args: object, **_kwargs: object) -> object:
            mapping = {
                "#agent-summary-panel": summary,
                "#memory-indicators": memory,
                "#task-list-widget": tasks,
                "#skill-components": skills,
                "#team-components": team,
                "#settings-panels": settings_panel,
            }
            return mapping[selector]

        with (
            patch.object(textual_app, "query_one", side_effect=query_one),
            patch("henchman.cli.textual_mixins.TaskService") as task_service,
            patch("henchman.cli.textual_mixins.SkillCatalog") as skill_catalog,
            patch("henchman.cli.textual_mixins.TeamWorkspaceService") as team_service,
        ):
            task_service.return_value.list_tasks.return_value = [
                MagicMock(task_id="task-1", status="running", title="Lint"),
            ]
            skill_catalog.return_value.list_skills.return_value = [
                SimpleNamespace(name="qa"),
                SimpleNamespace(name="design-review"),
            ]
            team_service.return_value.list_workspaces.return_value = [
                SimpleNamespace(name="core-team", members=("matt", "copilot")),
            ]

            textual_app._refresh_workspace_widgets()

        summary.update_summary.assert_called_once()
        memory.update_counts.assert_called_once_with(
            session_messages=4,
            history_entries=2,
            context_loaded=True,
        )
        tasks.set_tasks.assert_called_once()
        skills.set_skills.assert_called_once_with(["qa", "design-review"])
        team.set_workspaces.assert_called_once_with(["core-team (2 members)"])
        settings_panel.update_settings.assert_called_once()

    def test_refresh_workspace_widgets_uses_real_settings_and_session_state(
        self,
        textual_app: HenchmanTextualApp,
    ) -> None:
        """Workspace status must read the real Settings and runtime schemas."""

        textual_app.settings = Settings(ui={"theme": "dracula"})
        textual_app.config = TextualConfig(auto_approve_tools=False)
        current_session = Session(
            id="settings-session",
            project_hash="project-1",
            started="2026-09-03T10:00:00+00:00",
            last_updated="2026-09-03T10:01:00+00:00",
            plan_mode=True,
        )
        textual_app.core_context = MagicMock(
            session_manager=MagicMock(current=current_session),
            tool_manager=MagicMock(auto_approve=True),
            mcp_manager=None,
        )
        summary = AgentSummaryPanel()
        settings_panel = SettingsPanel()

        def query_widget(_app: object, selector: str, _widget_type: type) -> object | None:
            widgets = {
                "#agent-summary-panel": summary,
                "#settings-panels": settings_panel,
            }
            return widgets.get(selector)

        with patch(
            "henchman.cli.textual_mixins._query_one_or_none",
            side_effect=query_widget,
        ):
            textual_app._refresh_workspace_widgets()

        assert "Mode: Plan" in summary.render()
        rendered_settings = settings_panel.render()
        assert "Theme: dracula" in rendered_settings
        assert "Auto: enabled" in rendered_settings

    @pytest.mark.anyio
    async def test_workspace_missing_required_metadata_stays_live_with_error(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Incomplete valid workspace JSON must not abort the Textual mount."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        metadata_path = tmp_path / ".henchman" / "team" / "workspaces" / "broken" / "workspace.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text('{"name": "broken"}', encoding="utf-8")

        with (
            patch.object(textual_app, "_initialize_core_components"),
            patch.object(textual_app, "_populate_context_tree"),
            patch.object(textual_app, "_show_welcome"),
            patch.object(textual_app, "_load_history"),
        ):
            try:
                async with textual_app.run_test(size=(120, 50)) as pilot:
                    await pilot.pause()
                    rendered = textual_app.query_one(
                        "#team-components",
                        TeamPanel,
                    ).render()
                    notifications = list(textual_app._notifications)
            except KeyError as exc:
                pytest.fail(f"invalid workspace metadata escaped to Textual: {exc}")

        assert "Failed to load teams" in rendered
        assert "No teams" not in rendered
        assert any("Failed to load teams" in item.message for item in notifications)

    def test_refresh_workspace_widgets_reports_malformed_skill_state(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Malformed persisted skills must not be rendered as a real empty state."""

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path))
        skill_path = tmp_path / ".henchman" / "skills" / "broken.yaml"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text("name: [unterminated", encoding="utf-8")
        skill_widget = SkillPanel()

        def query_widget(_app: object, selector: str, _widget_type: type) -> object | None:
            return skill_widget if selector == "#skill-components" else None

        with patch(
            "henchman.cli.textual_mixins._query_one_or_none",
            side_effect=query_widget,
        ):
            try:
                textual_app._refresh_workspace_widgets()
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f"workspace refresh escaped to Textual: {exc}")

        rendered = skill_widget.render()
        assert "Failed to load skills" in rendered
        assert "No skills" not in rendered

    @pytest.mark.anyio
    async def test_refresh_workspace_widgets_reads_real_project_services(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Workspace panels must render actual persisted project data."""

        monkeypatch.chdir(tmp_path)
        task_service = TaskService(project_root=tmp_path)
        task = await task_service.start_task(
            argv=[sys.executable, "-c", "print('operational')"],
            title="Operational lint",
        )
        await task_service.wait_for_task(task.task_id, timeout=10)

        skill_path = tmp_path / ".henchman" / "skills" / "review.yaml"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(
            "name: review\ndescription: Review the current change\n",
            encoding="utf-8",
        )
        TeamWorkspaceService(project_root=tmp_path).create_workspace(
            name="core-team",
            members=["matt", "henchman"],
        )

        task_widget = TaskListWidget()
        skill_widget = SkillPanel()
        team_widget = TeamPanel()
        widgets = {
            "#task-list-widget": task_widget,
            "#skill-components": skill_widget,
            "#team-components": team_widget,
        }

        def query_widget(_app: object, selector: str, _widget_type: type) -> object | None:
            return widgets.get(selector)

        with patch(
            "henchman.cli.textual_mixins._query_one_or_none",
            side_effect=query_widget,
        ):
            textual_app._refresh_workspace_widgets()

        assert "Operational lint" in task_widget.render()
        assert "review" in skill_widget.render()
        assert "core-team" in team_widget.render()

    def test_build_bridge_dialog_entries_uses_persisted_bridge_metadata(
        self,
        textual_app: HenchmanTextualApp,
    ) -> None:
        with (
            patch("henchman.cli.textual_mixins.TeamWorkspaceService") as team_service,
            patch("henchman.cli.textual_mixins.BridgeSessionService") as bridge_service,
        ):
            team_service.return_value.list_workspaces.return_value = [
                SimpleNamespace(name="core-team", workspace_id="core-team"),
                SimpleNamespace(name="ops", workspace_id="ops"),
            ]
            bridge_service.return_value.list_bridges.side_effect = [
                [
                    SimpleNamespace(
                        bridge_id="bridge-1",
                        status="active",
                        remote_session="remote-123",
                        created_by="matt",
                    ),
                ],
                [],
            ]

            entries = textual_app._build_bridge_dialog_entries()

        assert entries == ["core-team / bridge-1 (active) - remote-123 by matt"]

    def test_build_bridge_dialog_entries_reads_real_project_services(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Bridge dialog entries must come from persisted team metadata."""

        monkeypatch.chdir(tmp_path)
        workspace = TeamWorkspaceService(project_root=tmp_path).create_workspace(
            name="ops-team",
            members=["matt"],
        )
        BridgeSessionService(project_root=tmp_path).open_bridge(
            workspace_id=workspace.workspace_id,
            remote_session="remote-session-1",
            created_by="matt",
        )

        entries = textual_app._build_bridge_dialog_entries()

        assert len(entries) == 1
        assert "ops-team" in entries[0]
        assert "remote-session-1" in entries[0]

    def test_handle_export_result_writes_markdown_export_for_active_session(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        current_session = MagicMock()
        current_session.id = "session-123"
        session_manager = MagicMock(current=current_session)
        textual_app.core_context = MagicMock(session_manager=session_manager)
        chat = MagicMock()

        with (
            patch.object(textual_app, "query_one", return_value=chat),
            patch(
                "henchman.cli.textual_mixins.export_as_markdown", return_value="# Export"
            ) as export,
        ):
            textual_app._handle_export_result("markdown")

        output_path = tmp_path / "session_session-123.md"
        assert output_path.read_text(encoding="utf-8") == "# Export"
        export.assert_called_once_with(current_session, include_metadata=True)
        chat.add_system_message.assert_called_once()

    def test_handle_export_result_serializes_real_session_content(
        self,
        textual_app: HenchmanTextualApp,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Textual export must use the production Markdown serializer."""

        monkeypatch.chdir(tmp_path)
        current_session = Session(
            id="session-real",
            project_hash="project-1",
            started="2026-09-03T10:00:00+00:00",
            last_updated="2026-09-03T10:01:00+00:00",
            messages=[SessionMessage(role="user", content="Prove this session works")],
        )
        textual_app.core_context = MagicMock(
            session_manager=MagicMock(current=current_session),
        )
        chat = MagicMock()

        with patch.object(textual_app, "query_one", return_value=chat):
            textual_app._handle_export_result("markdown")

        output = (tmp_path / "session_session-real.md").read_text(encoding="utf-8")
        assert "## Conversation" in output
        assert "Prove this session works" in output

    def test_handle_export_result_reports_missing_active_session(
        self,
        textual_app: HenchmanTextualApp,
    ) -> None:
        textual_app.core_context = MagicMock(session_manager=MagicMock(current=None))
        chat = MagicMock()

        with patch.object(textual_app, "query_one", return_value=chat):
            textual_app._handle_export_result("json")

        chat.add_error_message.assert_called_once_with(
            "Failed to export session: No active session to export.",
        )

    def test_onboarding_settings_opens_workspace_overview(
        self,
        textual_app: HenchmanTextualApp,
    ) -> None:
        tabs = MagicMock()
        tabs.active = "tab-chat"

        with (
            patch.object(textual_app, "query_one", return_value=tabs),
            patch.object(textual_app, "_refresh_workspace_widgets") as refresh,
        ):
            textual_app._handle_onboarding_result("settings")

        assert tabs.active == "tab-workspace"
        refresh.assert_called_once()

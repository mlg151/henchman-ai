"""Tier 8 ops spine tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from henchman.cli.system_info import HealthSignal, InstallContext, SystemInfo
from henchman.ops.flags import FeatureFlagService
from henchman.ops.migrations import Migration, MigrationRunner
from henchman.ops.native import NativeBindings
from henchman.ops.observability import (
    AnalyticsService,
    CostTrackingService,
    DiagnosticTrackingService,
    TelemetryService,
)
from henchman.ops.state import AppStateStore
from henchman.ops.store import OpsStore
from henchman.ops.sync import SettingsSyncBackend
from henchman.ops.updater import AutoUpdater


def _write_settings(settings_dir: Path, payload: dict[str, object]) -> None:
    """Write a settings file for sync tests."""
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "settings.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=True),
        encoding="utf-8",
    )


def test_app_state_store_selectors_and_migrations(tmp_path: Path) -> None:
    """App state should support selectors and schema migrations."""
    store = OpsStore(db_path=tmp_path / "ops.db")
    app_state = AppStateStore(store=store)

    app_state.set("ui.theme", "monokai")
    app_state.set("api.proxy.base_url", "https://proxy.example")

    assert app_state.get("ui.theme") == "monokai"
    assert app_state.select(prefix="ui.") == {"ui.theme": "monokai"}

    runner = MigrationRunner(
        store=store,
        namespace="app_state",
        migrations=[
            Migration(
                version=1,
                name="seed-diagnostics-flag",
                apply=lambda state: state.set("diagnostics.enabled", True),
            )
        ],
    )

    applied = runner.migrate(app_state)

    assert applied == ["seed-diagnostics-flag"]
    assert app_state.get("diagnostics.enabled") is True
    assert runner.current_version() == 1


def test_settings_sync_backend_round_trip_is_file_based(tmp_path: Path) -> None:
    """Settings sync backend should round-trip via the existing file repository."""
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    source_root.mkdir()
    destination_root.mkdir()

    _write_settings(
        source_root / ".henchman",
        {"ui": {"output_style": "json", "theme": "monokai", "keybindings": {"c-j": "accept"}}},
    )

    backend = SettingsSyncBackend()
    payload = backend.export_project_settings(project_root=source_root)
    backend.import_project_settings(project_root=destination_root, payload=payload)

    assert backend.export_project_settings(project_root=destination_root) == payload


def test_observability_services_record_analytics_telemetry_costs_and_diagnostics(
    tmp_path: Path,
) -> None:
    """Observability services should persist the core Tier 8 event types."""
    store = OpsStore(db_path=tmp_path / "ops.db")
    analytics = AnalyticsService(store=store)
    telemetry = TelemetryService(store=store)
    costs = CostTrackingService(store=store)
    diagnostics = DiagnosticTrackingService(store=store)

    analytics.record("session_started", {"project": "demo"})
    telemetry.record("remote_session.create", tokens=120, tool_calls=2)
    amount = costs.record_usage(
        provider="deepseek",
        model="deepseek-chat",
        prompt_tokens=100,
        completion_tokens=50,
    )
    diagnostics.record("proxy_configured", status="pass", details={"base_url": "https://proxy"})

    assert analytics.count("session_started") == 1
    assert telemetry.list_events()[0]["payload"]["tool_calls"] == 2
    assert amount > 0
    assert costs.summary()["total_cost"] == amount
    assert diagnostics.list_events(status="pass")[0]["event_type"] == "proxy_configured"


def test_feature_flags_native_bindings_and_auto_updater(tmp_path: Path) -> None:
    """Feature flags, native bindings, and updater checks should share a minimal ops contract."""
    store = OpsStore(db_path=tmp_path / "ops.db")
    flags = FeatureFlagService(
        store=store,
        env={"HENCHMAN_FLAG_EXPERIMENTAL_API": "1"},
    )
    flags.set_flag("desktop_bridge", False)

    assert flags.is_enabled("experimental_api") is True
    assert flags.is_enabled("desktop_bridge") is False

    native = NativeBindings(module_loader=lambda _name: (_ for _ in ()).throw(ImportError("missing")))
    capabilities = native.capabilities()
    assert capabilities["color_diff"]["available"] is False
    assert capabilities["color_diff"]["backend"] == "python"

    system_info = SystemInfo(
        package_name="henchman-ai",
        version="0.3.17",
        install_context=InstallContext(
            install_method="pip",
            package_manager="pip",
            executable_path="/workspace/.venv/bin/henchman",
            python_executable="/workspace/.venv/bin/python",
        ),
        health_signals=(HealthSignal(name="package-manager", status="pass", summary="ok"),),
    )
    updater = AutoUpdater(
        system_info_getter=lambda: system_info,
        latest_version_fetcher=lambda _package: "9.9.9",
    )
    result = updater.check()

    assert result["update_available"] is True
    assert result["plan"].can_self_update is True
    assert result["plan"].rendered_command.endswith("henchman-ai")

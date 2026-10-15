"""Tests for the Tier 8 serve command."""

from click.testing import CliRunner


def test_serve_command_invokes_run_server(monkeypatch) -> None:
    """serve should forward CLI options to the API server runner."""
    from henchman.cli.serve import serve_command

    captured: dict[str, object] = {}

    def _run_server(*, host: str, port: int, reload: bool, workers: int) -> None:
        captured.update(
            {"host": host, "port": port, "reload": reload, "workers": workers},
        )

    monkeypatch.setattr("henchman.cli.serve.run_server", _run_server)

    runner = CliRunner()
    result = runner.invoke(
        serve_command,
        ["--host", "0.0.0.0", "--port", "9001", "--reload", "--workers", "2"],
    )

    assert result.exit_code == 0
    assert captured == {"host": "0.0.0.0", "port": 9001, "reload": True, "workers": 2}

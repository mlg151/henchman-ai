from pathlib import Path
from unittest.mock import MagicMock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.chat import ChatCommand
from henchman.core.session import SessionManager


@pytest.mark.asyncio
async def test_resume_session_by_short_id(tmp_path):
    # Setup session manager with temp directory
    manager = SessionManager(data_dir=tmp_path)

    # Create and save a session
    project_hash = "test-project"
    session = manager.create_session(project_hash)
    session_id = session.id
    short_id = session_id[:8]
    manager.save(session)

    # Verify session file exists
    assert (tmp_path / f"{session_id}.json").exists()

    # Setup mock context
    console = MagicMock()
    ctx = CommandContext(
        args=["resume", short_id],
        console=console,
        agent=MagicMock(),
        repl=MagicMock(),
    )
    ctx.session_manager = manager
    ctx.project_hash = project_hash

    # Execute resume command
    command = ChatCommand()
    await command.execute(ctx)

    # Check if session was loaded (it should fail with current implementation)
    # console.print should have been called with an error message if it failed
    error_calls = [
        call for call in console.print.call_args_list if "Session not found" in str(call)
    ]

    if error_calls:
        print(f"Failed to resume with short ID: {short_id}")
    else:
        print(f"Successfully resumed with short ID: {short_id}")

    # Assert it succeeded
    assert not any("Session not found" in str(call) for call in console.print.call_args_list)
    assert any("Resumed session" in str(call) for call in console.print.call_args_list)


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_resume_session_by_short_id(Path("./tmp_sessions")))

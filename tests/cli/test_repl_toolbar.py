from unittest.mock import Mock, patch

import pytest

from henchman.cli.repl import Repl
from henchman.core.session import Session


@pytest.fixture
def repl():
    with patch("henchman.cli.repl.create_session"):
        provider = Mock()
        console = Mock()
        return Repl(provider=provider, console=console)

def test_get_toolbar_status_chat(repl):
    repl.session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    repl.session.plan_mode = False

    status = repl._get_toolbar_status()
    # Check for CHAT
    assert any("CHAT" in text for style, text in status)
    # Check for Tokens
    assert any("Tokens" in text for style, text in status)

def test_get_toolbar_status_plan(repl):
    repl.session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    repl.session.plan_mode = True

    status = repl._get_toolbar_status()
    # Check for PLAN MODE
    assert any("PLAN MODE" in text for style, text in status)

def test_get_toolbar_status_no_session(repl):
    repl.session = None
    status = repl._get_toolbar_status()
    assert any("CHAT" in text for style, text in status)

def test_get_toolbar_status_exception(repl):
    repl.session = Session(id="1", project_hash="abc", started="now", last_updated="now")
    # Force exception in count_messages
    with patch("henchman.utils.tokens.TokenCounter.count_messages", side_effect=Exception("error")):
        status = repl._get_toolbar_status()
        # Should still return mode but maybe skip tokens
        assert any("CHAT" in text for style, text in status)

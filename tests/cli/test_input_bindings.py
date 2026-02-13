from unittest.mock import Mock

import pytest
from prompt_toolkit.keys import Keys

from henchman.cli.input import create_session


def test_escape_key_clears_buffer():
    session = create_session()
    # Mock event
    event = Mock()
    event.current_buffer.text = "some input"

    # Get the handler for Escape
    # prompt_toolkit bindings are stored in session.key_bindings
    # We can trigger it manually if we find it

    kb = session.key_bindings
    # Find handler for Escape
    # For prompt_toolkit 3.0+
    for binding in kb.bindings:
        if binding.keys == (Keys.Escape,):
            handler = binding.handler
            handler(event)
            break
    else:
        pytest.fail("Escape handler not found")

    assert event.current_buffer.text == ""


def test_escape_key_empty_buffer():
    """Escape on empty buffer calls app.exit(result='') for graceful exit."""
    session = create_session()
    event = Mock()
    event.current_buffer.text = ""

    kb = session.key_bindings
    for binding in kb.bindings:
        if binding.keys == (Keys.Escape,):
            handler = binding.handler
            handler(event)
            break
    else:
        pytest.fail("Escape handler not found")

    # Verify app.exit was called with empty string
    event.app.exit.assert_called_once_with(result="")


def test_ctrl_c_raises_keyboard_interrupt():
    """Ctrl+C raises KeyboardInterrupt for clean exit."""
    session = create_session()
    event = Mock()

    kb = session.key_bindings
    for binding in kb.bindings:
        if binding.keys == (Keys.ControlC,):
            handler = binding.handler
            with pytest.raises(KeyboardInterrupt):
                handler(event)
            break
    else:
        pytest.fail("Ctrl+C handler not found")

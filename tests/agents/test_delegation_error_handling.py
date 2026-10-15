"""Tests for delegation error handling bug fix."""

from unittest.mock import MagicMock

from henchman.agents.delegation import _collect_tool_errors, _fetch_agent_errors, _get_status_value


def test_fetch_agent_errors_with_get_delegation_errors():
    """Test _fetch_agent_errors when agent has get_delegation_errors method."""
    mock_agent = MagicMock()
    mock_agent.get_delegation_errors.return_value = ["error1", "error2"]
    # Remove _delegation_tool_errors attribute if it exists
    if hasattr(mock_agent, '_delegation_tool_errors'):
        delattr(mock_agent, '_delegation_tool_errors')

    result = _fetch_agent_errors(mock_agent)
    assert result == ["error1", "error2"]
    mock_agent.get_delegation_errors.assert_called_once()


def test_fetch_agent_errors_with_delegation_tool_errors_attr():
    """Test _fetch_agent_errors when agent has _delegation_tool_errors attribute."""
    mock_agent = MagicMock()
    # Remove get_delegation_errors method
    delattr(mock_agent, 'get_delegation_errors')
    mock_agent._delegation_tool_errors = ["error3", "error4"]

    result = _fetch_agent_errors(mock_agent)
    assert result == ["error3", "error4"]


def test_fetch_agent_errors_with_no_error_methods():
    """Test _fetch_agent_errors when agent has no error methods."""
    mock_agent = MagicMock()
    # Remove both methods
    delattr(mock_agent, 'get_delegation_errors')
    if hasattr(mock_agent, '_delegation_tool_errors'):
        delattr(mock_agent, '_delegation_tool_errors')

    result = _fetch_agent_errors(mock_agent)
    assert result == []


def test_fetch_agent_errors_with_none_errors():
    """Test _fetch_agent_errors when errors is None."""
    mock_agent = MagicMock()
    mock_agent.get_delegation_errors.return_value = None
    if hasattr(mock_agent, '_delegation_tool_errors'):
        delattr(mock_agent, '_delegation_tool_errors')

    result = _fetch_agent_errors(mock_agent)
    assert result == []


def test_fetch_agent_errors_with_non_list_errors():
    """Test _fetch_agent_errors when errors is not a list."""
    mock_agent = MagicMock()
    mock_agent.get_delegation_errors.return_value = "not a list"
    if hasattr(mock_agent, '_delegation_tool_errors'):
        delattr(mock_agent, '_delegation_tool_errors')

    result = _fetch_agent_errors(mock_agent)
    assert result == []


def test_fetch_agent_errors_exception_handling():
    """Test _fetch_agent_errors exception handling."""
    mock_agent = MagicMock()
    mock_agent.get_delegation_errors.side_effect = Exception("Test error")
    if hasattr(mock_agent, '_delegation_tool_errors'):
        delattr(mock_agent, '_delegation_tool_errors')

    result = _fetch_agent_errors(mock_agent)
    assert result == []


def test_collect_tool_errors():
    """Test _collect_tool_errors function."""
    # Test with normal strings
    result = _collect_tool_errors(["error1", "error2"])
    assert result == ["error1", "error2"]

    # Test with None items
    result = _collect_tool_errors(["error1", None, "error2"])
    assert result == ["error1", "error2"]

    # Test with non-string items that can be converted
    result = _collect_tool_errors(["error1", 123, "error2"])
    assert result == ["error1", "123", "error2"]

    # Test with items that can't be converted to string
    class Unstringifiable:
        def __str__(self):
            raise TypeError("Cannot convert")

    result = _collect_tool_errors(["error1", Unstringifiable(), "error2"])
    assert result == ["error1", "error2"]


def test_get_status_value():
    """Test _get_status_value function for coverage."""
    # Test with object that has .value attribute
    class StatusWithValue:
        value = "status_value"

    result = _get_status_value(StatusWithValue())
    assert result == "status_value"

    # Test with object that doesn't have .value but can be stringified
    class StatusWithoutValue:
        def __str__(self):
            return "string_status"

    result = _get_status_value(StatusWithoutValue())
    assert result == "string_status"

    # Test with None
    result = _get_status_value(None)
    assert result == "UNKNOWN_STATUS"

    # Test with object that raises exception when stringified
    class BadStatus:
        def __str__(self):
            raise Exception("Cannot stringify")

    result = _get_status_value(BadStatus())
    assert result == "UNKNOWN_STATUS"

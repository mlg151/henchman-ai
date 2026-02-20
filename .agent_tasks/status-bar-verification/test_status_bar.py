#!/usr/bin/env python3
"""Test script to verify the enhanced status bar functionality."""

import sys
from unittest.mock import Mock, patch
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from henchman.cli.repl import Repl
from henchman.core.session import Session
from henchman.utils.tokens import TokenCounter


def test_status_bar_components():
    """Test that all status bar components are present and correct."""
    print("Testing enhanced status bar functionality...")
    
    # Create a mock provider
    provider = Mock()
    provider.__class__.__name__ = "DeepSeekProvider"
    provider.default_model = "deepseek-chat"
    
    # Create a mock console
    console = Mock()
    
    # Create REPL instance with mocked dependencies
    with patch("henchman.cli.repl.create_session"):
        repl = Repl(provider=provider, console=console)
        
        # Set up session
        session = Session(id="test-1", project_hash="abc", started="now", last_updated="now")
        session.plan_mode = False
        repl.session_manager.session = session
        
        # Mock tool registry
        repl.tool_registry = Mock()
        repl.tool_registry.list_tools.return_value = ["read_file", "write_file", "edit_file", "ls", "grep", "shell"]
        
        # Mock settings with max_tokens
        settings = Mock()
        context = Mock()
        context.max_tokens = 10000
        settings.context = context
        repl.settings = settings
        
        # Mock agent messages
        repl.agent = Mock()
        repl.agent.get_messages_for_api.return_value = [
            Mock(role="system", content="You are a helpful assistant."),
            Mock(role="user", content="Hello!"),
            Mock(role="assistant", content="Hi there!"),
        ]
        
        # Mock MCP manager
        mcp_manager = Mock()
        client1 = Mock()
        client1.is_connected = True
        client2 = Mock()
        client2.is_connected = False
        client3 = Mock()
        client3.is_connected = True
        mcp_manager.clients = {"server1": client1, "server2": client2, "server3": client3}
        repl.mcp_manager = mcp_manager
        
        # Get status bar with mocked token counting
        with patch("henchman.utils.tokens.TokenCounter.count_messages") as mock_count:
            mock_count.return_value = 3000  # 30% of 10000
            status = repl._get_toolbar_status()
        
        print(f"\nStatus bar items ({len(status)} total):")
        for i, item in enumerate(status):
            print(f"  {i}: Item={item}")
            if isinstance(item, tuple) and len(item) == 2:
                style, text = item
                print(f"     Style={style[:30]}..., Text={text}")
            else:
                print(f"     Unexpected item format: {type(item)}")
        
        # Verify all expected components
        components_found = {
            "CHAT/PLAN MODE": False,
            "Provider:Model": False,
            "Token percentage": False,
            "Tool count": False,
            "MCP status": False,
        }
        
        for item in status:
            if isinstance(item, tuple) and len(item) == 2:
                style, text = item
                if "CHAT" in text or "PLAN MODE" in text:
                    components_found["CHAT/PLAN MODE"] = True
                if "DeepSeek:deepseek-chat" in text:
                    components_found["Provider:Model"] = True
                if "%" in text and "Tokens" in text:
                    components_found["Token percentage"] = True
                if "Tools:" in text and "6" in text:  # 6 tools mocked
                    components_found["Tool count"] = True
                if "MCP:" in text and "2/3" in text:  # 2 connected out of 3
                    components_found["MCP status"] = True
        
        print("\nComponent verification:")
        all_passed = True
        for component, found in components_found.items():
            status = "✓" if found else "✗"
            print(f"  {status} {component}")
            if not found:
                all_passed = False
        
        # Test token percentage color coding
        print("\nTesting token percentage color coding:")
        token_items = []
        for item in status:
            if isinstance(item, tuple) and len(item) == 2:
                style, text = item
                print(f"  Checking item: text='{text}', has 'Tokens'={'Tokens' in text}, has '%'={'%' in text}")
                if "Tokens" in text and "%" in text:
                    token_items.append((style, text))
        
        print(f"  Found {len(token_items)} token items")
        if token_items:
            token_style, token_text = token_items[0]
            print(f"  Token style: {token_style}")
            print(f"  Token text: {token_text}")
            # Check if color is in style (green, yellow, or red)
            if "green" in token_style or "yellow" in token_style or "red" in token_style:
                print("  ✓ Token percentage has color coding")
            else:
                print("  ✗ Token percentage missing color coding")
                all_passed = False
        else:
            print("  ✗ No token percentage found")
            all_passed = False
        
        # Test edge cases
        print("\nTesting edge cases:")
        
        # Test without MCP manager
        repl.mcp_manager = None
        status_no_mcp = repl._get_toolbar_status()
        has_mcp = any("MCP:" in text for style, text in status_no_mcp)
        if not has_mcp:
            print("  ✓ MCP status not shown when manager is None")
        else:
            print("  ✗ MCP status shown when manager is None")
            all_passed = False
        
        # Test without settings
        repl.settings = None
        with patch("henchman.utils.tokens.TokenCounter.count_messages") as mock_count:
            mock_count.return_value = 3000
            status_no_settings = repl._get_toolbar_status()
        has_percentage = any("%" in text and "Tokens" in text for style, text in status_no_settings)
        has_count = any("Tokens:" in text and "%" not in text for style, text in status_no_settings)
        if not has_percentage and has_count:
            print("  ✓ Falls back to token count when no settings")
        else:
            print("  ✗ Should fall back to token count when no settings")
            all_passed = False
        
        return all_passed


def test_provider_name_extraction():
    """Test provider name extraction from different provider class names."""
    print("\nTesting provider name extraction:")
    
    test_cases = [
        ("DeepSeekProvider", "DeepSeek"),
        ("AnthropicProvider", "Anthropic"),
        ("OpenAICompatibleProvider", "OpenAICompatible"),
        ("OllamaProvider", "Ollama"),
        ("CustomProvider", "Custom"),
        ("Provider", ""),  # Edge case
    ]
    
    all_passed = True
    for class_name, expected in test_cases:
        provider = Mock()
        provider.__class__.__name__ = class_name
        provider.default_model = "test-model"
        
        with patch("henchman.cli.repl.create_session"):
            repl = Repl(provider=provider, console=Mock())
            repl.session_manager.session = Mock()
            repl.session_manager.session.plan_mode = False
            
            status = repl._get_toolbar_status()
            provider_texts = [text for style, text in status if expected in text or expected == ""]
            
            if expected:
                if provider_texts:
                    print(f"  ✓ {class_name} -> {expected}")
                else:
                    print(f"  ✗ {class_name} -> {expected} (not found)")
                    all_passed = False
            else:
                # For empty expected, just check it doesn't crash
                print(f"  ✓ {class_name} handled without crash")
    
    return all_passed


if __name__ == "__main__":
    print("=" * 60)
    print("Enhanced Status Bar Verification")
    print("=" * 60)
    
    test1_passed = test_status_bar_components()
    test2_passed = test_provider_name_extraction()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Status bar components: {'PASS' if test1_passed else 'FAIL'}")
    print(f"  Provider name extraction: {'PASS' if test2_passed else 'FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
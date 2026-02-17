#!/bin/bash
echo "Testing Serena MCP server integration..."

# Check if uvx works
if command -v uvx &> /dev/null; then
    echo "✅ uvx is available"
    
    # Try to get Serena help
    echo "Testing Serena installation..."
    if timeout 10 uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help &> /dev/null; then
        echo "✅ Serena can be installed via uvx"
    else
        echo "⚠️  Serena installation test timed out or failed"
        echo "This might be a network issue. Serena will install on first use."
    fi
else
    echo "❌ uvx not found in PATH"
    echo "Please ensure uv is installed and in your PATH"
fi

echo ""
echo "To use Serena with Henchman-AI:"
echo "1. Start Henchman-AI: mlg"
echo "2. Check MCP status: /mcp list"
echo "3. List tools: /tools"
echo ""
echo "If Serena doesn't appear in /mcp list, check:"
echo "- uv is installed: curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "- Network connectivity"
echo "- Settings file at ~/.henchman/settings.yaml"

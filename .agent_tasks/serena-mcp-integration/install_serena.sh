#!/bin/bash
# Installation script for Serena MCP server integration with Henchman-AI

set -e

echo "🔧 Installing Serena MCP server integration for Henchman-AI"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add to PATH if installed in ~/.cargo/bin
    if [ -f "$HOME/.cargo/bin/uv" ]; then
        export PATH="$HOME/.cargo/bin:$PATH"
        echo "✅ Added uv to PATH"
    fi
else
    echo "✅ uv is already installed"
fi

# Verify uv installation
if ! uvx --version &> /dev/null; then
    echo "❌ uvx command not found after installation"
    echo "Please ensure uv is in your PATH and try again"
    exit 1
fi

echo "✅ uv installation verified"

# Test Serena installation
echo "🧪 Testing Serena installation..."
if uvx --from git+https://github.com/oraios/serena serena start-mcp-server --help &> /dev/null; then
    echo "✅ Serena can be installed via uvx"
else
    echo "⚠️  Serena installation test failed"
    echo "This might be a network issue. Continuing anyway..."
fi

# Create settings directory if it doesn't exist
SETTINGS_DIR="$HOME/.henchman"
if [ ! -d "$SETTINGS_DIR" ]; then
    echo "📁 Creating settings directory: $SETTINGS_DIR"
    mkdir -p "$SETTINGS_DIR"
fi

# Check if settings file exists
SETTINGS_FILE="$SETTINGS_DIR/settings.yaml"
if [ -f "$SETTINGS_FILE" ]; then
    echo "📄 Existing settings file found: $SETTINGS_FILE"
    echo "Please add Serena configuration manually:"
    echo ""
    echo "mcp_servers:"
    echo "  serena:"
    echo "    command: uvx"
    echo "    args: [\"--from\", \"git+https://github.com/oraios/serena\", \"serena\", \"start-mcp-server\"]"
    echo "    trusted: true"
    echo ""
else
    echo "📝 Creating example settings file: $SETTINGS_FILE"
    cat > "$SETTINGS_FILE" << 'EOF'
# Henchman-AI settings with Serena MCP server
providers:
  default: deepseek
  deepseek:
    model: deepseek-chat
    api_key: "${DEEPSEEK_API_KEY}"

tools:
  shell_timeout: 60
  auto_approve_read: true

mcp_servers:
  # Serena - Semantic code retrieval and editing
  serena:
    command: uvx
    args: ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"]
    trusted: true

ui:
  theme: default
  show_thoughts: true
  streaming: true
EOF
    echo "✅ Created settings file with Serena configuration"
fi

# Create a test script to verify installation
echo "🧪 Creating verification script..."
cat > test_serena.sh << 'EOF'
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
echo "1. Start Henchman-AI: henchman"
echo "2. Check MCP status: /mcp list"
echo "3. List tools: /tools"
echo ""
echo "If Serena doesn't appear in /mcp list, check:"
echo "- uv is installed: curl -LsSf https://astral.sh/uv/install.sh | sh"
echo "- Network connectivity"
echo "- Settings file at ~/.henchman/settings.yaml"
EOF

chmod +x test_serena.sh
echo "✅ Created test script: ./test_serena.sh"

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Next steps:"
echo "1. Run the test script: ./test_serena.sh"
echo "2. Start Henchman-AI: henchman"
echo "3. In Henchman-AI, run: /mcp list"
echo "4. If Serena appears, run: /tools to see available tools"
echo ""
echo "For more information, see:"
echo "- Serena documentation: https://oraios.github.io/serena/"
echo "- Henchman-AI MCP integration: .github/copilot-instructions.md"
echo ""
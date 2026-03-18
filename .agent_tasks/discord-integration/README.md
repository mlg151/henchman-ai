# Discord Integration for Henchman-AI

## Goal
Create a Discord bot that allows remote interaction with Henchman-AI from anywhere, authenticated to a specific user (matthew.l.glover@gmail.com).

## Architecture
- Discord bot using `discord.py` library (optional dependency)
- Integrates with Henchman-AI's Agent system
- Streams responses in chunks (Discord 2000 char limit)
- DM-only mode for security (only responds to authorized user)
- Slash commands for common operations (/help, /clear, /status, /history)

## Implementation Details

### Files Created
- `src/henchman/chat/__init__.py` - Module init with lazy imports for Discord
- `src/henchman/chat/base.py` - Base abstractions (ChatBot, ChatMessage, ChatPlatform)
- `src/henchman/chat/discord_bot.py` - Discord bot implementation
- `src/henchman/chat/manager.py` - Chat manager coordinating bots with agents
- `src/henchman/cli/chat_serve.py` - CLI command to start the bot
- `tests/chat/test_chat.py` - Comprehensive test suite

### Configuration
Added to `config/schema.py`:
- `DiscordSettings` - discord.enabled, token, allowed_user_id, system_prompt
- `ChatConfig` - Container for chat settings
- Added `chat: ChatConfig` to `Settings`

### Installation
```bash
pip install henchman-ai[discord]  # Optional dependency
```

### Usage
```bash
# Set environment variables
export DISCORD_TOKEN="your-bot-token"
export DISCORD_USER_ID="your-discord-user-id"

# Or pass via CLI
henchman chat-serve --token "xxx" --user-id "yyy"

# Or configure in settings.yaml
henchman chat-serve
```

## Status
- [x] Create base chat abstraction
- [x] Implement Discord bot
- [x] Create chat manager
- [x] Add CLI command (`henchman chat-serve`)
- [x] Write tests
- [ ] Integration testing with live Discord bot

## Setup Instructions
1. Go to https://discord.com/developers/applications
2. Click "New Application" and give it a name
3. Go to "Bot" section
4. Click "Reset Token" and copy the token
5. Enable "Message Content Intent" under Privileged Gateway Intents
6. Your User ID: Right-click your username in Discord (Developer Mode enabled) → Copy User ID
7. Invite bot to a DM or server

## Key Decisions
- Using discord.py (most popular, well-maintained Python library)
- DM-only mode for security (only responds to authorized user)
- discord.py is an optional dependency - not required for core Henchman-AI
- Streaming responses split into multiple messages (2000 char limit)
- Per-user agent sessions maintained by ChatManager

"""Chat manager for coordinating chat bot integrations with Henchman-AI."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from henchman.chat.base import ChatMessage, ChatPlatform
from henchman.core.events import EventType
from henchman.providers import get_default_registry
from henchman.providers.utils import get_api_key_for_provider

if TYPE_CHECKING:
    from henchman.chat.base import ChatBot
    from henchman.config import Settings
    from henchman.core import Agent

logger = logging.getLogger(__name__)


class ChatManager:
    """Manages chat bot integrations and connects them to Henchman-AI agents.

    This class:
    1. Creates and manages chat bot instances
    2. Connects incoming messages to Henchman-AI agents
    3. Streams agent responses back to users
    4. Maintains per-user agent sessions

    Attributes:
        settings: Henchman-AI settings.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize the chat manager.

        Args:
            settings: Henchman-AI settings loaded from configuration.
        """
        self._settings = settings
        self._bots: dict[ChatPlatform, ChatBot] = {}
        self._user_agents: dict[str, Agent] = {}  # user_id -> Agent
        self._user_histories: dict[str, list[dict[str, Any]]] = {}  # user_id -> messages

    def create_discord_bot(
        self,
        token: str,
        allowed_user_id: str,
    ) -> Any:
        """Create and configure a Discord bot.

        Args:
            token: Discord bot token.
            allowed_user_id: Discord user ID authorized to use the bot.

        Returns:
            Configured DiscordBot instance.

        Raises:
            ImportError: If discord.py is not installed.
        """
        from henchman.chat.discord_bot import DiscordBot

        bot = DiscordBot(
            token=token,
            allowed_user_id=allowed_user_id,
        )
        bot.set_message_handler(self._handle_message)
        self._bots[ChatPlatform.DISCORD] = bot
        return bot

    async def _get_or_create_agent(self, user_id: str) -> Agent:
        """Get or create an agent for a user.

        Args:
            user_id: User identifier.

        Returns:
            Agent instance for the user.
        """
        from henchman.core import Agent

        if user_id in self._user_agents:
            return self._user_agents[user_id]

        # Create new agent for user
        registry = get_default_registry()
        provider_name = self._settings.providers.default

        # Get provider settings
        provider_settings = self._get_provider_settings(provider_name)

        provider = registry.create(provider_name, **provider_settings)

        # Use custom system prompt if configured
        system_prompt = (
            "You are Henchman-AI, a helpful AI assistant accessible via chat. "
            "You have access to a full suite of tools for file operations, code execution, "
            "web search, git operations, and more. You can help with coding, research, "
            "analysis, and automation tasks. "
            "When using tools, explain what you're doing and why. "
            "Keep responses concise but informative. "
            "Use markdown formatting for code blocks and structure."
        )

        # Override with Discord-specific system prompt if configured
        if (
            hasattr(self._settings, "chat")
            and hasattr(self._settings.chat, "discord")
            and self._settings.chat.discord.system_prompt
        ):
            system_prompt = self._settings.chat.discord.system_prompt

        # Register built-in tools for the agent
        from henchman.cli.tool_manager import ToolManager

        tool_manager = ToolManager(self._settings)
        tool_manager.register_builtin_tools()

        # Auto-approve all tools for Discord (non-interactive mode)
        tool_manager.set_auto_approve(auto_approve=True)

        agent = Agent(
            provider=provider,
            system_prompt=system_prompt,
            tool_registry=tool_manager.registry,
        )

        self._user_agents[user_id] = agent
        self._user_histories[user_id] = []

        logger.info("Created new agent for user %s with %d tools",
                    user_id, len(tool_manager.registry.list_tools()))
        return agent

    def _get_provider_defaults(self, provider_name: str) -> dict[str, Any]:
        """Get default settings for a provider.

        Args:
            provider_name: Name of the provider.

        Returns:
            Dictionary of default provider settings.
        """
        defaults: dict[str, Any] = {}

        # Add API key from environment if available
        api_key = get_api_key_for_provider(provider_name)
        if api_key:
            defaults["api_key"] = api_key

        # Add provider-specific defaults
        if provider_name == "deepseek":
            defaults.setdefault("model", "deepseek-chat")
        elif provider_name == "ollama":
            defaults.setdefault("model", "llama3.2")
        elif provider_name == "anthropic":
            defaults.setdefault("model", "claude-3-5-sonnet-20241022")
        elif provider_name == "openai_compat":
            # For generic OpenAI-compatible, we need at least a model
            defaults.setdefault("model", "gpt-4o-mini")
        elif provider_name == "openrouter":
            defaults.setdefault("model", "openai/gpt-4o-mini")
        elif provider_name == "together":
            defaults.setdefault("model", "meta-llama/Llama-3.2-3B-Instruct-Turbo")
        elif provider_name == "groq":
            defaults.setdefault("model", "llama-3.1-8b-instant")
        elif provider_name == "fireworks":
            defaults.setdefault("model", "accounts/fireworks/models/llama-v3p1-8b-instruct")

        return defaults

    def _get_provider_settings(self, provider_name: str) -> dict[str, Any]:
        """Get provider settings for the given provider name.

        Args:
            provider_name: Name of the provider.

        Returns:
            Dictionary of provider settings.
        """
        provider_settings_map = {
            "deepseek": "deepseek",
            "openai": "openai",
            "anthropic": "anthropic",
            "ollama": "ollama",
            "openrouter": "openrouter",
            "openai_compat": "openai_compat",
            "together": "together",
            "groq": "groq",
            "fireworks": "fireworks",
        }

        if provider_name not in provider_settings_map:
            return {}

        settings_attr = provider_settings_map[provider_name]
        provider_settings = getattr(self._settings.providers, settings_attr, None)

        if provider_settings is not None:
            # Handle case where provider_settings is not a dict
            # (e.g., string from misconfigured YAML)
            if isinstance(provider_settings, dict):
                return dict(provider_settings)
            else:
                # Log warning and return defaults
                logger.warning(
                    "Provider '%s' settings is not a dictionary (type: %s). "
                    "Using defaults instead. Please fix configuration.",
                    provider_name,
                    type(provider_settings).__name__,
                )
                # Return defaults directly instead of falling through
                # to avoid duplicate warning
                return self._get_provider_defaults(provider_name)

        # Provider settings are missing - return reasonable defaults
        # This fixes the bug where empty dict {} was returned
        defaults = self._get_provider_defaults(provider_name)

        logger.warning(
            "Provider '%s' is configured as default but has no settings. "
            "Using defaults: %s. Please configure provider settings in your configuration.",
            provider_name,
            {k: "***" if "key" in k.lower() else v for k, v in defaults.items()},
        )

        return defaults

    async def _process_stream(
        self,
        agent: Agent,
        bot: Any,
        user_id: str,
        stream: Any,
        response_parts: list[str],
        current_chunk: str,
        max_iterations: int = 2500,
    ) -> tuple[list[str], str, bool]:
        """Process an agent stream, executing tool calls and collecting content.

        Args:
            agent: The agent instance.
            bot: The chat bot instance.
            user_id: The user ID.
            stream: Async iterator of agent events.
            response_parts: List to collect response chunks.
            current_chunk: Current content chunk being accumulated.
            max_iterations: Safety limit to prevent infinite loops (events per turn).

        Returns:
            Tuple of (response_parts, current_chunk, had_tool_calls).
        """
        iteration = 0
        had_tool_calls = False
        async for event in stream:
            iteration += 1
            if iteration > max_iterations:
                logger.warning("Max stream iterations reached for user %s", user_id)
                await bot.send_message(
                    user_id,
                    "⚠️ Maximum response length exceeded. Stopping.",
                )
                break

            if event.type == EventType.CONTENT:
                current_chunk += event.data

                # Check if we should flush the chunk
                # We want to avoid splitting inside a code block if possible,
                # unless the chunk is getting too large (letting the bot handle strict splitting)
                should_flush = False
                chunk_len = len(current_chunk)

                if chunk_len >= 1800:
                    # Basic check: are we inside a code block?
                    # Count odd number of code fences
                    is_in_code_block = current_chunk.count("```") % 2 != 0

                    if not is_in_code_block:
                        should_flush = True
                    elif chunk_len >= 2500:
                        # Safety limit: if it's getting huge, flush anyway and let the bot's
                        # internal splitter handle the markdown logic (since it handles >2000 chars)
                        should_flush = True

                if should_flush:
                    await bot.send_message(user_id, current_chunk)
                    response_parts.append(current_chunk)
                    current_chunk = ""

            elif event.type == EventType.TOOL_CALL_REQUEST:
                had_tool_calls = True

                # Flush any pending content
                if current_chunk:
                    await bot.send_message(user_id, current_chunk)
                    response_parts.append(current_chunk)
                    current_chunk = ""

                # Execute the tool call
                tool_call = event.data
                tool_name = getattr(tool_call, "name", "unknown")
                tool_args = getattr(tool_call, "arguments", {})
                tool_id = getattr(tool_call, "id", "unknown")

                # Notify user about the tool call
                await bot.send_message(
                    user_id,
                    f"🔧 Running: `{tool_name}`",
                )

                try:
                    # Execute the tool
                    result = await agent.tool_registry.execute(tool_name, tool_args)

                    # Truncate very long results for display
                    result_content = result.content
                    if len(result_content) > 1500:
                        display_result = result_content[:1500] + "\n... (truncated)"
                    else:
                        display_result = result_content

                    await bot.send_message(
                        user_id,
                        f"✅ Result:\n```\n{display_result}\n```",
                    )

                    # Submit result back to the agent
                    agent.submit_tool_result(tool_id, result.content)

                except Exception as tool_err:
                    logger.exception(
                        "Tool execution failed: %s for user %s", tool_name, user_id
                    )
                    error_msg = f"❌ Tool `{tool_name}` failed: {tool_err}"
                    try:
                        await bot.send_message(user_id, error_msg)
                    except Exception as send_err:
                        logger.warning(
                            "Failed to send error message to user %s: %s",
                            user_id,
                            send_err,
                        )
                        # Continue anyway - we still need to submit the tool result

                    # Submit error to agent so it can recover
                    agent.submit_tool_result(tool_id, f"Error: {tool_err}")

            elif event.type == EventType.TOOL_CALL_RESULT:
                # Continue the agent after tool results
                # This is handled by submit_tool_result + continue_with_tool_results
                pass

            elif event.type == EventType.FINISHED:
                break

            elif event.type == EventType.ERROR:
                logger.error("Agent error for user %s: %s", user_id, event.data)
                await bot.send_message(user_id, f"❌ Error: {event.data}")
                break

        return response_parts, current_chunk, had_tool_calls

    async def _handle_message(self, message: ChatMessage) -> None:
        """Handle an incoming chat message with full tool execution support.

        This method implements the complete agent loop:
        1. Streams the agent's response
        2. Detects tool call requests
        3. Executes tools using the tool registry
        4. Submits results back to the agent
        5. Continues the agent loop until finished

        Args:
            message: The incoming chat message.

        Returns:
            None
        """
        logger.info(
            "Received message from %s (ID: %s): %s",
            message.username,
            message.user_id,
            message.content[:100],
        )

        # Handle special commands
        if message.content.startswith("/"):
            await self._handle_command(message)
            return

        # Get or create agent for user
        agent = await self._get_or_create_agent(message.user_id)

        # Get the bot for this platform
        bot = self._bots.get(message.platform)
        if not bot:
            logger.error("No bot found for platform %s", message.platform)
            return

        # Send typing indicator
        await bot.send_typing(message.user_id)

        # Collect response parts
        response_parts: list[str] = []
        current_chunk = ""

        try:
            # Main agent loop: run -> tool calls -> continue -> tool calls -> ...
            stream = agent.run(user_input=message.content)
            max_continuation_rounds = 20  # Safety limit on tool continuation rounds

            for _round in range(max_continuation_rounds + 1):
                response_parts, current_chunk, had_tool_calls = await self._process_stream(
                    agent, bot, message.user_id, stream, response_parts, current_chunk
                )

                # Only continue if tool calls were made and results submitted
                if not had_tool_calls:
                    break

                # Continue the agent with the submitted tool results
                stream = agent.continue_with_tool_results()
            else:
                logger.warning(
                    "Max continuation rounds reached for user %s", message.user_id
                )
                await bot.send_message(
                    message.user_id,
                    "⚠️ Maximum tool rounds reached. Stopping.",
                )

            # Send remaining content
            if current_chunk:
                await bot.send_message(message.user_id, current_chunk)
                response_parts.append(current_chunk)

            # Store in history
            if response_parts:
                self._user_histories.setdefault(message.user_id, []).extend(
                    [
                        {"role": "user", "content": message.content},
                        {"role": "assistant", "content": "\n".join(response_parts)},
                    ]
                )

        except Exception:
            logger.exception("Error processing message from %s", message.user_id)
            await bot.send_message(
                message.user_id,
                "❌ Sorry, an error occurred while processing your request. Please try again.",
            )

    async def _handle_command(self, message: ChatMessage) -> None:
        """Handle special chat commands.

        Args:
            message: The incoming chat message.

        Returns:
            None
        """
        bot = self._bots.get(message.platform)
        if not bot:
            return

        parts = message.content.split()
        command = parts[0].lower()
        _args = parts[1:]  # Reserved for future use

        if command == "/help":
            help_text = (
                "**Henchman-AI Commands**\n\n"
                "`/help` - Show this help message\n"
                "`/clear` - Clear conversation history\n"
                "`/status` - Show bot status and stats\n"
                "`/history` - Show conversation history summary\n\n"
                "**Usage:**\n"
                "Just type your message and I'll respond! I can help with:\n"
                "• Code questions and programming\n"
                "• File operations and shell commands\n"
                "• Web research and information\n"
                "• Analysis and problem-solving"
            )
            await bot.send_message(message.user_id, help_text)

        elif command == "/clear":
            if message.user_id in self._user_agents:
                self._user_agents[message.user_id].clear_history()
            self._user_histories[message.user_id] = []
            await bot.send_message(
                message.user_id,
                "✅ Conversation history cleared!",
            )

        elif command == "/status":
            agent = self._user_agents.get(message.user_id)
            provider_name = self._settings.providers.default
            history_count = len(self._user_histories.get(message.user_id, []))

            status_text = (
                "**Henchman-AI Status**\n\n"
                f"• **Provider:** {provider_name}\n"
                f"• **Agent:** {'Active' if agent else 'Not initialized'}\n"
                f"• **Messages in history:** {history_count}\n"
                f"• **Platform:** {message.platform.value}"
            )
            await bot.send_message(message.user_id, status_text)

        elif command == "/history":
            history = self._user_histories.get(message.user_id, [])
            if not history:
                await bot.send_message(
                    message.user_id,
                    "No conversation history yet.",
                )
                return

            # Show last 5 exchanges
            recent = history[-10:]  # Last 5 exchanges (user + assistant)
            history_text = "**Recent Conversation:**\n\n"
            for msg in recent:
                role = "**You:**" if msg["role"] == "user" else "**Henchman:**"
                content = msg["content"][:100] + ("..." if len(msg["content"]) > 100 else "")
                history_text += f"{role} {content}\n\n"

            await bot.send_message(message.user_id, history_text)

        else:
            await bot.send_message(
                message.user_id,
                f"❓ Unknown command: `{command}`. Type `/help` for available commands.",
            )

    async def start_all(self) -> None:
        """Start all configured bots.

        Returns:
            None
        """
        tasks = []
        for bot in self._bots.values():
            logger.info("Starting %s bot...", bot.platform.value)
            tasks.append(asyncio.create_task(bot.start()))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all running bots.

        Returns:
            None
        """
        for bot in self._bots.values():
            if bot.is_connected:
                logger.info("Stopping %s bot...", bot.platform.value)
                await bot.stop()

    @property
    def bots(self) -> dict[ChatPlatform, ChatBot]:
        """Get all configured bots.

        Returns:
            Dictionary mapping platforms to bot instances.
        """
        return self._bots

    @property
    def active_users(self) -> list[str]:
        """Get list of user IDs with active agents.

        Returns:
            List of user ID strings.
        """
        return list(self._user_agents.keys())

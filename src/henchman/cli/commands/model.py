"""Model and provider management commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from henchman.cli.commands import Command, CommandContext
from henchman.config import load_settings
from henchman.providers import get_default_registry

if TYPE_CHECKING:
    pass


class ModelCommand(Command):
    """Show or change the model and provider."""

    @property
    def name(self) -> str:
        """Command name.

        Returns:
            Command name string.
        """
        return "model"

    @property
    def description(self) -> str:
        """Command description.

        Returns:
            Description string.
        """
        return "Show or change the model and provider"

    @property
    def usage(self) -> str:
        """Command usage.

        Returns:
            Usage string.
        """
        return "/model [list|set <provider> [<model>]]"

    async def execute(self, ctx: CommandContext) -> None:
        """Execute the model command.

        Args:
            ctx: Command context.
        """
        args = ctx.args
        if not args:
            await self._show_current(ctx)
        elif args[0] == "list":
            await self._list_providers(ctx)
        elif args[0] == "set" and len(args) >= 2:
            await self._set_provider(ctx, args[1], args[2] if len(args) > 2 else None)
        else:
            ctx.console.print(f"[yellow]Usage: {self.usage}[/]")

    async def _show_current(self, ctx: CommandContext) -> None:
        """Show current provider and model.

        Args:
            ctx: Command context.
        """
        if not ctx.agent:
            ctx.console.print("[yellow]No active agent. Cannot show current model.[/]")
            return

        provider = ctx.agent.provider
        _settings = load_settings()
        registry = get_default_registry()
        available = registry.list_providers()

        self._print_current_configuration(ctx.console, provider, available)

    def _print_current_configuration(
        self, console: Any, provider: Any, available: list[str]
    ) -> None:
        """Print current provider and model configuration.

        Args:
            console: Console for output.
            provider: Current provider.
            available: List of available providers.
        """
        console.print("\n[bold blue]Current Configuration[/]\n")
        console.print(f"  Provider: [cyan]{provider.name}[/]")

        # Show model if available
        if hasattr(provider, "default_model"):
            console.print(f"  Model: [cyan]{provider.default_model}[/]")

        # Show available providers
        console.print(f"\n  Available providers: [dim]{', '.join(available)}[/]")
        console.print("\n  Use [cyan]/model list[/] to see all providers")
        console.print("  Use [cyan]/model set <provider> [model][/] to switch")
        console.print("")

    async def _list_providers(self, ctx: CommandContext) -> None:
        """List all available providers and models.

        Args:
            ctx: Command context.
        """
        registry = get_default_registry()
        providers = registry.list_providers()

        ctx.console.print("\n[bold blue]Available Providers[/]\n")

        for provider_name in sorted(providers):
            try:
                provider_class = registry.get(provider_name)

                # Get example configuration
                example_config = self._get_example_config(provider_name)

                ctx.console.print(f"  [cyan]{provider_name}[/]")
                if hasattr(provider_class, "__doc__") and provider_class.__doc__:
                    doc_lines = provider_class.__doc__.strip().split("\n")
                    first_line = doc_lines[0].strip()
                    ctx.console.print(f"    [dim]{first_line}[/]")

                if example_config:
                    ctx.console.print(f"    [yellow]Config:[/] {example_config}")

                # Show environment variables needed
                env_vars = self._get_env_vars(provider_name)
                if env_vars:
                    ctx.console.print(f"    [yellow]Env vars:[/] {env_vars}")

                ctx.console.print("")
            except Exception as e:
                ctx.console.print(f"  [red]{provider_name}[/] - Error: {e}")

    async def _set_provider(
        self, ctx: CommandContext, provider_name: str, model_name: str | None = None
    ) -> None:
        """Switch to a different provider.

        Args:
            ctx: Command context.
            provider_name: Name of the provider to switch to.
            model_name: Optional model name to use.

        Raises:
            ValueError: If provider cannot be created.
        """
        if not ctx.repl:
            ctx.console.print("[yellow]Cannot switch providers without REPL context.[/]")
            return

        try:
            # Validate provider exists
            if not self._validate_provider_exists(ctx, provider_name):
                return

            # Try to get API key from environment or settings
            api_key = self._get_api_key_for_provider(provider_name)

            # Create provider instance
            new_provider = self._create_provider_instance(provider_name, model_name, api_key)

            # Test the provider connection
            self._test_provider_connection(ctx, new_provider, provider_name, model_name)

            # Update the agent with new provider
            if not self._update_agent_provider(ctx, new_provider):
                return

            # Show any configuration needed
            self._show_configuration_warnings(ctx, provider_name, api_key)

        except Exception as e:
            ctx.console.print(f"[red]Failed to switch provider: {e}[/]")
            ctx.console.print("[dim]Check that the provider is properly configured.[/]")

    def _validate_provider_exists(self, ctx: CommandContext, provider_name: str) -> bool:
        """Validate that the provider exists in the registry.

        Args:
            ctx: Command context.
            provider_name: Name of the provider to validate.

        Returns:
            True if provider exists, False otherwise.
        """
        registry = get_default_registry()
        if provider_name not in registry.list_providers():
            ctx.console.print(f"[red]Provider '{provider_name}' not found.[/]")
            ctx.console.print(f"Available providers: {', '.join(registry.list_providers())}")
            return False
        return True

    def _create_provider_instance(
        self, provider_name: str, model_name: str | None, api_key: str | None
    ) -> Any:
        """Create a new provider instance.

        Args:
            provider_name: Name of the provider to create.
            model_name: Optional model name to use.
            api_key: API key for the provider.

        Returns:
            New provider instance.
        """
        registry = get_default_registry()
        provider_kwargs = {"api_key": api_key or ""}
        if model_name:
            provider_kwargs["model"] = model_name
        return registry.create(provider_name, **provider_kwargs)

    def _test_provider_connection(
        self, ctx: CommandContext, provider: Any, provider_name: str, model_name: str | None
    ) -> None:
        """Test provider connection and print results.

        Args:
            ctx: Command context.
            provider: Provider instance to test.
            provider_name: Name of the provider.
            model_name: Optional model name used.
        """
        ctx.console.print(f"[dim]Testing {provider_name} connection...[/]")
        try:
            # Simple test to verify provider works
            if hasattr(provider, "default_model"):
                ctx.console.print(f"[green]✓ Connected to {provider_name}[/]")
                if model_name:
                    ctx.console.print(f"[green]✓ Using model: {model_name}[/]")
                else:
                    ctx.console.print(f"[green]✓ Using default model: {provider.default_model}[/]")
            else:
                ctx.console.print(f"[green]✓ Connected to {provider_name}[/]")
        except Exception as e:
            ctx.console.print(f"[yellow]⚠ Connection test failed: {e}[/]")
            ctx.console.print("[yellow]Provider created but may not work correctly.[/]")

    def _update_agent_provider(self, ctx: CommandContext, new_provider: Any) -> bool:
        """Update agent with new provider.

        Args:
            ctx: Command context.
            new_provider: New provider instance.

        Returns:
            True if successful, False otherwise.
        """
        if ctx.agent is None:
            ctx.console.print("[red]No agent available[/]")
            return False

        old_provider = ctx.agent.provider
        ctx.agent.provider = new_provider

        # Update REPL's provider reference
        if ctx.repl is not None:
            ctx.repl.provider = new_provider

        ctx.console.print(
            f"\n[bold green]✓ Switched from {old_provider.name} to {new_provider.name}[/]"
        )
        return True

    def _show_configuration_warnings(
        self, ctx: CommandContext, provider_name: str, api_key: str | None
    ) -> None:
        """Show configuration warnings if API key is missing.

        Args:
            ctx: Command context.
            provider_name: Name of the provider.
            api_key: API key for the provider.
        """
        if not api_key:
            env_var = self._get_env_var_name(provider_name)
            ctx.console.print(f"\n[yellow]⚠ No API key found for {provider_name}[/]")
            ctx.console.print(f"  Set environment variable: [cyan]{env_var}=your-api-key[/]")
            ctx.console.print("  Or configure in [cyan]~/.henchman/settings.yaml[/]:")
            ctx.console.print("    providers:")
            ctx.console.print(f"      {provider_name}:")
            ctx.console.print("        api_key: your-api-key")

    def _get_example_config(self, provider_name: str) -> str:
        """Get example configuration for a provider.

        Args:
            provider_name: Name of the provider.

        Returns:
            Example configuration string.
        """
        examples = {
            "deepseek": "deepseek-chat (default), deepseek-coder",
            "openai": "gpt-4-turbo, gpt-3.5-turbo",
            "anthropic": "claude-3-opus, claude-3-sonnet",
            "ollama": "llama2, mistral, codellama",
        }
        return examples.get(provider_name, "Check provider documentation")

    def _get_env_vars(self, provider_name: str) -> str:
        """Get environment variables needed for a provider.

        Args:
            provider_name: Name of the provider.

        Returns:
            Environment variable names.
        """
        from henchman.providers.utils import get_env_var_for_provider

        # Special case for ollama since it doesn't need an API key
        if provider_name == "ollama":
            return "OLLAMA_HOST (optional, defaults to http://localhost:11434)"

        # Get the environment variable
        env_var = get_env_var_for_provider(provider_name)

        # If it's HENCHMAN_API_KEY and the provider is not one of the known
        # providers that use it, return a more helpful message
        if env_var == "HENCHMAN_API_KEY":
            # Known providers that use HENCHMAN_API_KEY
            known_henchman_providers = {
                "openai_compat",
                "together",
                "groq",
                "fireworks",
                "openrouter",
            }
            if provider_name not in known_henchman_providers and provider_name not in {
                "deepseek",
                "openai",
                "anthropic",  # These have their own env vars
            }:
                return "Check provider documentation"

        return env_var

    def _get_env_var_name(self, provider_name: str) -> str:
        """Get the environment variable name for a provider's API key.

        Args:
            provider_name: Name of the provider.

        Returns:
            Environment variable name.
        """
        from henchman.providers.utils import get_env_var_for_provider

        return get_env_var_for_provider(provider_name)

    def _get_api_key_for_provider(self, provider_name: str) -> str | None:
        """Get API key for a provider from environment or settings.

        Args:
            provider_name: Name of the provider.

        Returns:
            API key if found, None otherwise.
        """
        # Try environment variables first using utility function
        from henchman.providers.utils import get_api_key_for_provider

        api_key = get_api_key_for_provider(provider_name)
        if api_key:
            return api_key

        # Try settings
        try:
            settings = load_settings()
            provider_settings = getattr(settings.providers, provider_name, None)
            if provider_settings and hasattr(provider_settings, "api_key"):
                val = getattr(provider_settings, "api_key", None)
                if val is not None:
                    return str(val)
        except Exception:
            pass

        return None

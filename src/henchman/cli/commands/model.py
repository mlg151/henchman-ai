"""Model and provider management commands."""

from __future__ import annotations

from typing import Any

from henchman.cli.commands import Command, CommandContext
from henchman.config import load_settings
from henchman.providers import get_default_registry

# ── Module-level helpers (no Feature Envy — they don't belong to any single class) ──


def _get_example_config(provider_name: str) -> str:
    """Return example model names for well-known providers."""
    examples = {
        "deepseek": "deepseek-chat (default), deepseek-coder",
        "openai": "gpt-4-turbo, gpt-3.5-turbo",
        "anthropic": "claude-3-opus, claude-3-sonnet",
        "ollama": "llama2, mistral, codellama",
    }
    return examples.get(provider_name, "Check provider documentation")


def _get_env_var_name(provider_name: str) -> str:
    """Return the environment variable name for a provider's API key."""
    from henchman.providers.utils import get_env_var_for_provider  # noqa: PLC0415

    return get_env_var_for_provider(provider_name)


def _get_env_vars(provider_name: str) -> str:
    """Return environment variable description for a provider."""
    from henchman.providers.utils import get_env_var_for_provider  # noqa: PLC0415

    if provider_name == "ollama":
        return "OLLAMA_HOST (optional, defaults to http://localhost:11434)"

    env_var = get_env_var_for_provider(provider_name)

    if env_var == "HENCHMAN_API_KEY":
        _known_henchman = {
            "openai_compat",
            "together",
            "groq",
            "fireworks",
            "openrouter",
        }
        _own_env_var = {"deepseek", "openai", "anthropic"}
        if provider_name not in _known_henchman and provider_name not in _own_env_var:
            return "Check provider documentation"

    return env_var


def _get_api_key_for_provider(provider_name: str) -> str | None:
    """Return API key for a provider from environment or settings."""
    from henchman.providers.utils import get_api_key_for_provider  # noqa: PLC0415

    api_key = get_api_key_for_provider(provider_name)
    if api_key:
        return api_key

    try:
        settings = load_settings()
        provider_settings = getattr(settings.providers, provider_name, None)
        if provider_settings and hasattr(provider_settings, "api_key"):
            val = getattr(provider_settings, "api_key", None)
            if val is not None:
                return str(val)
    except Exception:  # noqa: BLE001
        pass

    return None


def _print_current_configuration(
    console: Any, provider: Any, available: list[str],
) -> None:
    """Print current provider and model configuration."""
    console.print("\n[bold blue]Current Configuration[/]\n")
    console.print(f"  Provider: [cyan]{provider.name}[/]")
    if hasattr(provider, "default_model"):
        console.print(f"  Model: [cyan]{provider.default_model}[/]")
    console.print(f"\n  Available providers: [dim]{', '.join(available)}[/]")
    console.print("\n  Use [cyan]/model list[/] to see all providers")
    console.print("  Use [cyan]/model set <provider> [model][/] to switch")
    console.print("")


def _print_provider_entry(
    console: Any, provider_name: str, provider_class: Any,
) -> None:
    """Print a single provider entry in the listing."""
    console.print(f"  [cyan]{provider_name}[/]")
    if hasattr(provider_class, "__doc__") and provider_class.__doc__:
        first_line = provider_class.__doc__.strip().split("\n")[0].strip()
        console.print(f"    [dim]{first_line}[/]")
    example_config = _get_example_config(provider_name)
    if example_config:
        console.print(f"    [yellow]Config:[/] {example_config}")
    env_vars = _get_env_vars(provider_name)
    if env_vars:
        console.print(f"    [yellow]Env vars:[/] {env_vars}")
    console.print("")


async def _show_current(ctx: CommandContext) -> None:
    """Show current provider and model."""
    if not ctx.agent:
        ctx.console.print("[yellow]No active agent. Cannot show current model.[/]")
        return
    provider = ctx.agent.provider
    available = get_default_registry().list_providers()
    _print_current_configuration(ctx.console, provider, available)


async def _list_providers(ctx: CommandContext) -> None:
    """List all available providers and models."""
    registry = get_default_registry()
    console = ctx.console
    console.print("\n[bold blue]Available Providers[/]\n")
    for provider_name in sorted(registry.list_providers()):
        try:
            provider_class = registry.get(provider_name)
            _print_provider_entry(console, provider_name, provider_class)
        except Exception as e:  # noqa: BLE001, PERF203
            console.print(f"  [red]{provider_name}[/] - Error: {e}")


def _test_provider_connection(
    console: Any,
    provider: Any,
    provider_name: str,
    model_name: str | None,
) -> None:
    """Test provider connection and print results."""
    console.print(f"[dim]Testing {provider_name} connection...[/]")
    try:
        if hasattr(provider, "default_model"):
            console.print(f"[green]✓ Connected to {provider_name}[/]")
            if model_name:
                console.print(f"[green]✓ Using model: {model_name}[/]")
            else:
                console.print(
                    f"[green]✓ Using default model: {provider.default_model}[/]",
                )
        else:
            console.print(f"[green]✓ Connected to {provider_name}[/]")
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]⚠ Connection test failed: {e}[/]")
        console.print("[yellow]Provider created but may not work correctly.[/]")


def _update_agent_provider(ctx: CommandContext, new_provider: Any) -> bool:
    """Update agent with new provider; return True on success."""
    console = ctx.console
    if ctx.agent is None:
        console.print("[red]No agent available[/]")
        return False
    old_provider = ctx.agent.provider
    ctx.agent.provider = new_provider
    if ctx.repl is not None:
        ctx.repl.provider = new_provider
    console.print(
        f"\n[bold green]✓ Switched from {old_provider.name} to {new_provider.name}[/]",
    )
    return True


def _show_configuration_warnings(
    ctx: CommandContext,
    provider_name: str,
    api_key: str | None,
) -> None:
    """Show configuration warnings if API key is missing."""
    if api_key:
        return
    env_var = _get_env_var_name(provider_name)
    console = ctx.console
    console.print(f"\n[yellow]⚠ No API key found for {provider_name}[/]")
    console.print(f"  Set environment variable: [cyan]{env_var}=your-api-key[/]")
    console.print("  Or configure in [cyan]~/.henchman/settings.yaml[/]:")
    console.print("    providers:")
    console.print(f"      {provider_name}:")
    console.print("        api_key: your-api-key")


def _validate_provider_exists(ctx: CommandContext, provider_name: str) -> bool:
    """Validate provider exists in the registry; prints error and returns False if not."""
    registry = get_default_registry()
    if provider_name not in registry.list_providers():
        ctx.console.print(f"[red]Provider '{provider_name}' not found.[/]")
        ctx.console.print(
            f"Available providers: {', '.join(registry.list_providers())}",
        )
        return False
    return True


def _create_provider_instance(
    provider_name: str,
    model_name: str | None,
    api_key: str | None,
) -> Any:
    """Create and return a new provider instance."""
    registry = get_default_registry()
    provider_kwargs: dict[str, Any] = {"api_key": api_key or ""}
    if model_name:
        provider_kwargs["model"] = model_name
    return registry.create(provider_name, **provider_kwargs)


# ── Command class (thin orchestrator only) ──────────────────────────────────────


class ModelCommand(Command):
    """Show or change the model and provider."""

    _MIN_SET_ARGS = 2

    @property
    def name(self: ModelCommand) -> str:
        """Command name."""
        return "model"

    @property
    def description(self: ModelCommand) -> str:
        """Command description."""
        return "Show or change the model and provider"

    @property
    def usage(self: ModelCommand) -> str:
        """Command usage."""
        return "/model [list|set <provider> [<model>]]"

    async def execute(self: ModelCommand, ctx: CommandContext) -> None:
        """Execute the model command.

        Args:
            ctx: Command context.
        """
        args = ctx.args
        if not args:
            await _show_current(ctx)
        elif args[0] == "list":
            await _list_providers(ctx)
        elif args[0] == "set" and len(args) >= self._MIN_SET_ARGS:
            model = args[2] if len(args) > self._MIN_SET_ARGS else None
            await self._set_provider(ctx, args[1], model)
        else:
            ctx.console.print(f"[yellow]Usage: {self.usage}[/]")

    async def _set_provider(
        self: ModelCommand,
        ctx: CommandContext,
        provider_name: str,
        model_name: str | None = None,
    ) -> None:
        """Switch to a different provider.

        Args:
            ctx: Command context.
            provider_name: Name of the provider to switch to.
            model_name: Optional model name to use.
        """
        if not ctx.repl:
            ctx.console.print(
                "[yellow]Cannot switch providers without REPL context.[/]",
            )
            return

        try:
            if not _validate_provider_exists(ctx, provider_name):
                return

            api_key = _get_api_key_for_provider(provider_name)
            new_provider = _create_provider_instance(provider_name, model_name, api_key)
            _test_provider_connection(
                ctx.console, new_provider, provider_name, model_name,
            )

            if not _update_agent_provider(ctx, new_provider):
                return

            _show_configuration_warnings(ctx, provider_name, api_key)

        except Exception as e:  # noqa: BLE001
            ctx.console.print(f"[red]Failed to switch provider: {e}[/]")
            ctx.console.print("[dim]Check that the provider is properly configured.[/]")

"""Model and provider management commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from henchman.cli.commands import Command, CommandContext
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.config import load_settings
from henchman.config.schema import ProviderSettings
from henchman.providers import get_default_registry
from henchman.providers.factory import create_configured_provider

# ── Module-level helpers (no Feature Envy — not class methods) ──────────────────


@dataclass
class ProviderConfig:
    """Groups provider selection parameters to avoid Primitive Obsession.

    Attributes:
        name: Provider name.
        model: Optional model override.
        api_key: Optional API key.
    """

    name: str
    model: str | None
    api_key: str | None


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
    from henchman.providers.utils import get_env_var_for_provider

    return get_env_var_for_provider(provider_name)


def _get_env_vars(provider_name: str) -> str:
    """Return environment variable description for a provider."""
    from henchman.providers.utils import get_env_var_for_provider

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
    from henchman.providers.utils import get_api_key_for_provider

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
    except Exception:
        pass

    return None


def _print_current_configuration(
    console: Any,
    provider: Any,
    available: list[str],
) -> None:
    """Print current provider and model configuration."""
    console.print("\n[bold blue]Current Configuration[/]\n")
    console.print(f"  Provider: [cyan]{provider.name}[/]")
    if hasattr(provider, "default_model"):
        console.print(f"  Model: [cyan]{provider.default_model}[/]")
    console.print(f"\n  Available providers: [dim]{', '.join(available)}[/]")
    console.print("\n  Use [cyan]/model list[/] to see all providers")
    console.print("  Use [cyan]/model set <provider> [model] [--context-length <tokens>][/] to switch")
    console.print("")


def _print_provider_entry(
    console: Any,
    provider_name: str,
    provider_class: Any,
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
    _show_context_limits(ctx)


def _show_context_limits(ctx: CommandContext) -> None:
    """Show the selected session capacity and effective conversation budget."""
    settings = getattr(ctx.repl, "settings", None) if ctx.repl is not None else ctx.settings
    if settings is not None:
        ctx.console.print(f"  Context length: {settings.context.max_tokens} tokens (session)")
    if ctx.agent is not None:
        ctx.console.print(f"  Conversation budget: {ctx.agent.max_tokens} tokens")


async def _list_providers(ctx: CommandContext) -> None:
    """List all available providers and models."""
    registry = get_default_registry()
    console = ctx.console
    console.print("\n[bold blue]Available Providers[/]\n")
    for provider_name in sorted(registry.list_providers()):
        try:
            provider_class = registry.get(provider_name)
            _print_provider_entry(console, provider_name, provider_class)
        except Exception as e:
            console.print(f"  [red]{provider_name}[/] - Error: {e}")


def _show_provider_configuration(
    console: Any,
    provider: Any,
    provider_name: str,
    model_name: str | None,
) -> None:
    """Report local configuration without implying a network connection was tested."""
    console.print(f"[green]✓ Configured {provider_name} (connection not tested)[/]")
    effective_model = model_name or getattr(provider, "default_model", None)
    if effective_model:
        console.print(f"[green]✓ Using model: {effective_model}[/]")


def _update_agent_provider(
    ctx: CommandContext, new_provider: Any, *, context_length: int | None = None,
) -> bool:
    """Update agent with new provider; return True on success."""
    console = ctx.console
    if ctx.agent is None:
        console.print("[red]No agent available[/]")
        return False
    old_provider = ctx.agent.provider
    if ctx.repl is not None:
        switch_runtime_provider(
            ctx.repl, new_provider, agent=ctx.agent, context_length=context_length,
        )
    else:
        ctx.agent.set_provider(new_provider)
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
    config: ProviderConfig,
    settings: ProviderSettings | None = None,
) -> Any:
    """Create a provider using the selected runtime's saved configuration."""
    return create_configured_provider(
        settings if settings is not None else load_settings().providers,
        provider_name=config.name,
        model=config.model,
        api_key=config.api_key,
        registry=get_default_registry(),
    )


async def _set_provider(
    ctx: CommandContext,
    provider_name: str,
    model_name: str | None = None,
    *,
    context_length: int | None = None,
) -> None:
    """Switch to a different provider.

    Args:
        ctx: Command context.
        provider_name: Name of the provider to switch to.
        model_name: Optional model name to use.
    """
    if not ctx.repl:
        ctx.console.print("[yellow]Cannot switch providers without REPL context.[/]")
        return

    try:
        if not _validate_provider_exists(ctx, provider_name):
            return

        settings = getattr(ctx.repl, "settings", None)
        if settings is None:
            settings = load_settings()
        new_provider = _create_provider_instance(
            ProviderConfig(provider_name, model_name, None),
            settings.providers,
        )
        _show_provider_configuration(ctx.console, new_provider, provider_name, model_name)

        if not _update_agent_provider(ctx, new_provider, context_length=context_length):
            return
        _show_context_limits(ctx)

    except Exception as e:
        ctx.console.print(f"[red]Failed to switch provider: {e}[/]")
        ctx.console.print("[dim]Check that the provider is properly configured.[/]")


# ── Command class (thin orchestrator only) ──────────────────────────────────────


def _parse_model_selection(args: list[str]) -> tuple[str, str | None, int | None]:
    """Parse positional model selection and an optional positive context length."""
    positional: list[str] = []
    context_length: int | None = None
    index = 0
    while index < len(args):
        value = args[index]
        if value == "--context-length" or value.startswith("--context-length="):
            if context_length is not None:
                raise ValueError("Provide --context-length only once")
            if value == "--context-length":
                index += 1
                if index >= len(args):
                    raise ValueError("--context-length requires a positive integer")
                raw_limit = args[index]
            else:
                raw_limit = value.split("=", 1)[1]
            try:
                context_length = int(raw_limit)
            except ValueError as exc:
                raise ValueError("--context-length requires a positive integer") from exc
            if context_length <= 0:
                raise ValueError("--context-length requires a positive integer")
        elif value.startswith("-"):
            raise ValueError(f"Unknown option: {value}")
        else:
            positional.append(value)
        index += 1
    if not 1 <= len(positional) <= 2:
        raise ValueError("Provide a provider and at most one model")
    return positional[0], positional[1] if len(positional) == 2 else None, context_length


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
        return "/model [list|set <provider> [<model>] [--context-length <tokens>]]"

    async def execute(self: ModelCommand, ctx: CommandContext) -> None:
        """Execute the model command.

        Args:
            ctx: Command context.

        Returns:
            None
        """
        args = ctx.args
        if not args:
            await _show_current(ctx)
        elif args[0] == "list":
            await _list_providers(ctx)
        elif args[0] == "set" and len(args) >= self._MIN_SET_ARGS:
            try:
                provider, model, context_length = _parse_model_selection(args[1:])
            except ValueError as exc:
                ctx.console.print(f"[yellow]{exc}. Usage: {self.usage}[/]")
                return
            await _set_provider(ctx, provider, model, context_length=context_length)
        else:
            ctx.console.print(f"[yellow]Usage: {self.usage}[/]")

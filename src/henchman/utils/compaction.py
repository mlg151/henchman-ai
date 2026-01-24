from typing import TYPE_CHECKING

from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    from henchman.providers.base import Message

class ContextCompactor:
    """Manages context size by pruning older messages."""

    def __init__(self, max_tokens: int = 8000) -> None:
        """Initialize compactor.

        Args:
            max_tokens: Maximum tokens to keep in context.
        """
        self.max_tokens = max_tokens
    def compact(self, messages: list['Message']) -> list['Message']:
        """Compact messages to fit within max_tokens.

        Always preserves system messages and the last user message.
        Prunes from the beginning of history (after system prompts).
        """
        if not messages:
            return []

        current_tokens = TokenCounter.count_messages(messages)
        if current_tokens <= self.max_tokens:
            return messages

        # Separate system messages and critical last message
        system_msgs = [m for m in messages if m.role == "system"]
        critical_msgs = []
        if messages[-1].role == "user":
            critical_msgs.append(messages[-1])

        # The rest are candidates for pruning
        candidates = [m for m in messages if m not in system_msgs and m not in critical_msgs]

        # Calculate fixed cost
        fixed_cost = TokenCounter.count_messages(system_msgs + critical_msgs)
        budget = self.max_tokens - fixed_cost

        if budget <= 0:
            # Degenerate case: essential messages already exceed limit
            return system_msgs + critical_msgs

        # Add candidates from end until budget full
        kept = []
        used = 0
        for msg in reversed(candidates):
            cost = TokenCounter.count_messages([msg])
            if used + cost <= budget:
                kept.append(msg)
                used += cost
            else:
                break

        # Reconstruct order
        result = system_msgs + list(reversed(kept)) + critical_msgs
        return result

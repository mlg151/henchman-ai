"""Test syntax of the problematic function."""

def _ensure_safety_limit(self, content: str) -> str:
    """Ensure content doesn't exceed safety limit.

    Args:
        content: The content to check.

    Returns:
        Content truncated to safety limit if necessary.
    """
    final_content_tokens = 0  # TokenCounter.count_text(content)
    if final_content_tokens > self.safety_limit:
        # This shouldn't happen, but as a safety fallback, truncate
        return content[:100]  # TokenCounter.truncate_text(content, self.safety_limit)
    return content

print("Test syntax is OK")
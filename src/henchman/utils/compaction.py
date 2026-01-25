from typing import TYPE_CHECKING

from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    from henchman.providers.base import Message


class MessageSequence:
    """Represents an atomic sequence of messages that must be kept together."""
    
    def __init__(self, messages: list['Message']):
        self.messages = messages
    
    @property
    def token_count(self) -> int:
        """Get the token count for this sequence."""
        return TokenCounter.count_messages(self.messages)
    
    @property
    def is_tool_sequence(self) -> bool:
        """Check if this sequence contains tool calls."""
        return any(
            msg.role == "assistant" and msg.tool_calls 
            for msg in self.messages
        )
    
    def __repr__(self) -> str:
        roles = [msg.role for msg in self.messages]
        return f"MessageSequence(roles={roles}, tokens={self.token_count})"


class ContextCompactor:
    """Manages context size by pruning older messages.
    
    Preserves atomic sequences, especially tool call sequences.
    """

    def __init__(self, max_tokens: int = 8000) -> None:
        """Initialize compactor.

        Args:
            max_tokens: Maximum tokens to keep in context.
        """
        self.max_tokens = max_tokens

    def _group_into_sequences(self, messages: list['Message']) -> list[MessageSequence]:
        """Group messages into atomic sequences that must be kept together.
        
        Rules:
        1. Each user message starts a new sequence (except the first)
        2. Assistant messages with tool_calls include all following tool messages
           for those specific tool calls
        3. Other messages continue the current sequence
        
        Args:
            messages: The messages to group.
            
        Returns:
            List of MessageSequence objects.
        """
        if not messages:
            return []
        
        sequences: list[MessageSequence] = []
        current_sequence: list['Message'] = []
        
        i = 0
        while i < len(messages):
            msg = messages[i]
            current_sequence.append(msg)
            
            # Check if this message starts a tool call sequence
            if msg.role == "assistant" and msg.tool_calls:
                # Get all tool call IDs from this assistant
                tool_call_ids = {tc.id for tc in msg.tool_calls}
                
                # Include all immediately following tool messages for these IDs
                j = i + 1
                while j < len(messages) and messages[j].role == "tool":
                    if messages[j].tool_call_id in tool_call_ids:
                        current_sequence.append(messages[j])
                        j += 1
                    else:
                        # Different tool call, start new sequence
                        break
                i = j
            else:
                i += 1
            
            # Start a new sequence on user messages (except at the very beginning)
            # This helps with more granular pruning
            if msg.role == "user" and i < len(messages):
                sequences.append(MessageSequence(current_sequence))
                current_sequence = []
        
        # Add the last sequence
        if current_sequence:
            sequences.append(MessageSequence(current_sequence))
        
        return sequences

    def compact(self, messages: list['Message']) -> list['Message']:
        """Compact messages to fit within max_tokens.

        Always preserves system messages and the last user message.
        Prunes from the beginning of history (after system prompts).
        Preserves tool call sequences as atomic units.

        Args:
            messages: The messages to compact.

        Returns:
            Compacted messages that fit within max_tokens.
        """
        if not messages:  # pragma: no cover
            return []

        current_tokens = TokenCounter.count_messages(messages)
        if current_tokens <= self.max_tokens:
            return messages

        # Group messages into atomic sequences
        sequences = self._group_into_sequences(messages)
        
        if not sequences:
            return []

        # Separate system messages (always kept)
        system_msgs = [msg for msg in messages if msg.role == "system"]
        system_tokens = TokenCounter.count_messages(system_msgs)
        
        # Identify the last sequence (critical to keep if it's a user message)
        last_sequence = sequences[-1]
        last_sequence_is_user = (
            last_sequence.messages and 
            last_sequence.messages[-1].role == "user"
        )
        
        # Calculate fixed cost (system + last sequence if it's user-initiated)
        fixed_tokens = system_tokens
        if last_sequence_is_user:
            fixed_tokens += last_sequence.token_count
        
        budget = self.max_tokens - fixed_tokens
        
        if budget <= 0:  # pragma: no cover
            # Degenerate case: essential messages already exceed limit
            result = system_msgs.copy()
            if last_sequence_is_user:
                result.extend(last_sequence.messages)
            return result

        # Keep sequences from the end until budget is full
        # We skip the last sequence if it's already accounted for as fixed
        sequences_to_consider = sequences[:-1] if last_sequence_is_user else sequences
        
        kept_sequences: list[MessageSequence] = []
        used_tokens = 0
        
        for seq in reversed(sequences_to_consider):
            if used_tokens + seq.token_count <= budget:
                kept_sequences.append(seq)
                used_tokens += seq.token_count
            else:
                # Can't fit this entire sequence, stop here
                # We don't split sequences
                break
        
        # Reconstruct messages in correct order
        result: list['Message'] = []
        
        # Add system messages first
        result.extend(system_msgs)
        
        # Add kept sequences in chronological order
        for seq in reversed(kept_sequences):
            result.extend(seq.messages)
        
        # Add the last sequence if it was user-initiated
        if last_sequence_is_user:
            result.extend(last_sequence.messages)
        
        return result

    def validate_compacted_sequence(self, messages: list['Message']) -> bool:
        """Validate that a message sequence follows OpenAI API rules.
        
        Args:
            messages: The messages to validate.
            
        Returns:
            True if the sequence is valid, False otherwise.
        """
        for i, msg in enumerate(messages):
            if msg.role == "tool":
                # Tool messages must follow assistant with tool_calls
                if i == 0:
                    return False
                prev_msg = messages[i-1]
                if prev_msg.role != "assistant" or not prev_msg.tool_calls:
                    return False
                
                # Tool call ID must match one of the assistant's tool calls
                tool_call_ids = {tc.id for tc in prev_msg.tool_calls}
                if msg.tool_call_id not in tool_call_ids:
                    return False
        
        # Additional check: assistant with tool_calls should have tool responses
        for i, msg in enumerate(messages):
            if msg.role == "assistant" and msg.tool_calls:
                tool_call_ids = {tc.id for tc in msg.tool_calls}
                j = i + 1
                while j < len(messages) and messages[j].role == "tool":
                    if messages[j].tool_call_id in tool_call_ids:
                        tool_call_ids.remove(messages[j].tool_call_id)
                    j += 1
                
                # If there are still tool calls without responses, it's invalid
                if tool_call_ids:
                    return False
        
        return True

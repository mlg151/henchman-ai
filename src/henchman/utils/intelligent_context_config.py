"""Configuration classes for intelligent context management."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, ClassVar, TypeVar

if TYPE_CHECKING:
    from typing import Self

V = TypeVar("V")  # Generic type variable for values


@dataclass
class IntelligentContextParams:
    """Parameters for initializing IntelligentContextManager.

    Groups the 5 primitive parameters that were duplicated in __init__ and _create_config
    to address primitive obsession code smell.

    Attributes:
        max_tokens: Maximum tokens to keep in context.
        max_protected_ratio: Maximum ratio of context that can be protected.
        importance_threshold: Minimum importance score to preserve a message.
        cluster_similarity_threshold: Similarity threshold for clustering messages.
        adaptive_compression: Whether to use adaptive compression techniques.
    """

    max_tokens: int | None = None
    max_protected_ratio: float | None = None
    importance_threshold: float | None = None
    cluster_similarity_threshold: float | None = None
    adaptive_compression: bool | None = None


@dataclass
class IntelligentContextConfig:
    """Configuration for intelligent context management.

    Attributes:
        max_tokens: Maximum tokens to keep in context.
        max_protected_ratio: Maximum ratio of context that can be protected.
            If protected zone exceeds this, oldest protected content is truncated.
        importance_threshold: Minimum importance score to preserve a message.
            Messages below this threshold are candidates for compression or removal.
        cluster_similarity_threshold: Similarity threshold for clustering messages.
            Higher values create more specific clusters.
        adaptive_compression: Whether to use adaptive compression techniques
            based on conversation structure and content type.
        safety_limit_ratio: Ratio of max_tokens to use as safety limit for
            individual messages (0.0-1.0).
        minimum_word_length: Minimum word length for keyword extraction in clustering.
        minimum_keyword_count_for_type_detection: Minimum keyword count for
            conversation type detection.
        max_topics_to_show_in_summary: Maximum number of topics to show in summary.
    """

    # Default values
    DEFAULT_MAX_TOKENS: ClassVar[int] = 8000
    DEFAULT_MAX_PROTECTED_RATIO: ClassVar[float] = 0.3
    DEFAULT_IMPORTANCE_THRESHOLD: ClassVar[float] = 0.5
    DEFAULT_CLUSTER_SIMILARITY_THRESHOLD: ClassVar[float] = 0.7
    DEFAULT_SAFETY_LIMIT_RATIO: ClassVar[float] = 0.75
    DEFAULT_MINIMUM_WORD_LENGTH: ClassVar[int] = 3
    DEFAULT_MINIMUM_SHARED_WORDS: ClassVar[int] = 2
    DEFAULT_CLUSTER_SIZE_BOOST_FACTOR: ClassVar[float] = 0.1
    DEFAULT_COMPRESSION_HIGH_THRESHOLD: ClassVar[float] = 0.6
    DEFAULT_COMPRESSION_MEDIUM_THRESHOLD: ClassVar[float] = 0.3
    DEFAULT_MINIMUM_KEYWORD_COUNT_FOR_TYPE_DETECTION: ClassVar[int] = 2
    DEFAULT_MAX_TOPICS_TO_SHOW_IN_SUMMARY: ClassVar[int] = 3

    # Instance attributes with defaults
    max_tokens: int = field(default=DEFAULT_MAX_TOKENS)
    max_protected_ratio: float = field(default=DEFAULT_MAX_PROTECTED_RATIO)
    importance_threshold: float = field(default=DEFAULT_IMPORTANCE_THRESHOLD)
    cluster_similarity_threshold: float = field(
        default=DEFAULT_CLUSTER_SIMILARITY_THRESHOLD,
    )
    adaptive_compression: bool = field(default=True)
    safety_limit_ratio: float = field(default=DEFAULT_SAFETY_LIMIT_RATIO)
    minimum_word_length: int = field(default=DEFAULT_MINIMUM_WORD_LENGTH)
    minimum_shared_words: int = field(default=DEFAULT_MINIMUM_SHARED_WORDS)
    cluster_size_boost_factor: float = field(default=DEFAULT_CLUSTER_SIZE_BOOST_FACTOR)
    compression_high_threshold: float = field(default=DEFAULT_COMPRESSION_HIGH_THRESHOLD)
    compression_medium_threshold: float = field(
        default=DEFAULT_COMPRESSION_MEDIUM_THRESHOLD,
    )
    minimum_keyword_count_for_type_detection: int = field(
        default=DEFAULT_MINIMUM_KEYWORD_COUNT_FOR_TYPE_DETECTION,
    )
    max_topics_to_show_in_summary: int = field(
        default=DEFAULT_MAX_TOPICS_TO_SHOW_IN_SUMMARY,
    )

    @classmethod
    def from_params(
        cls: type[Self],
        params: IntelligentContextParams,
        config: Self | None = None,
    ) -> Self:
        """Create configuration from params with proper default handling.

        Args:
            params: IntelligentContextParams object.
            config: Existing config object. If provided, returns it unchanged.

        Returns:
            IntelligentContextConfig object.
        """
        if config is not None:
            return config

        # Filter out None values to use defaults in the config constructor
        params_dict = {k: v for k, v in asdict(params).items() if v is not None}
        return cls(**params_dict)

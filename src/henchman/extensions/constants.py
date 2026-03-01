"""Constants for plugin management."""

from typing import Final


class PluginConstants:
    """Plugin-related constants."""
    
    # HTTP timeout for registry requests (seconds)
    REGISTRY_TIMEOUT: Final[int] = 30
    
    # Default page size for search results
    DEFAULT_PAGE_SIZE: Final[int] = 20
    
    # HTTP status codes
    HTTP_NOT_FOUND: Final[int] = 404
    
    # Database column indices for plugin_installations table
    DB_COL_NAME: Final[int] = 0
    DB_COL_METADATA_JSON: Final[int] = 1
    DB_COL_INSTALLED_AT: Final[int] = 2
    DB_COL_INSTALLED_VERSION: Final[int] = 3
    DB_COL_ENABLED: Final[int] = 4
    DB_COL_INSTALLATION_PATH: Final[int] = 5
    DB_COL_LAST_USED: Final[int] = 6
    
    # Installation constants
    GIT_CLONE_DEPTH: Final[int] = 1
    DEFAULT_GITHUB_BRANCH: Final[str] = "main"
    
    # Security constants
    DEFAULT_RISK_LEVEL: Final[str] = "medium"
    LOW_RISK_LEVEL: Final[str] = "low"
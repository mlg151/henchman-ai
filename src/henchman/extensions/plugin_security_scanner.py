"""Security scanner for Henchman-AI plugins."""

from __future__ import annotations

from henchman.extensions.constants import PluginConstants
from henchman.extensions.models import PluginInstallation, SecurityReport


class PluginSecurityScanner:
    """Security scanner for plugins.

    Extracted from PluginManager to reduce class size and improve separation of concerns.
    """

    def scan(self, installation: PluginInstallation) -> SecurityReport:
        """Run security scan on a plugin installation.

        Args:
            installation: Plugin installation to scan.

        Returns:
            SecurityReport with scan results.
        """
        warnings: list[str] = []
        errors: list[str] = []
        declared_permissions = installation.metadata.security.permissions

        self._perform_security_checks(installation, warnings, errors)
        risk_level = self._calculate_risk_level(warnings)

        return SecurityReport(
            plugin_name=installation.metadata.name,
            passed=len(errors) == 0,
            warnings=warnings,
            errors=errors,
            permissions_used=declared_permissions,
            risk_level=risk_level,
        )

    def _perform_security_checks(
        self,
        installation: PluginInstallation,
        warnings: list[str],
        errors: list[str],
    ) -> None:
        """Perform security checks on a plugin installation.

        Args:
            installation: Plugin installation to check.
            warnings: List to append warnings to.
            errors: List to append errors to.
        """
        # TODO: Implement actual security scanning
        # This is a placeholder implementation

        # Check permissions vs declared
        # TODO: Analyze code for actual permission usage

        # Simple checks
        if installation.metadata.security.requires_sandbox:
            warnings.append("Plugin requires sandboxed execution")

    def _calculate_risk_level(self, warnings: list[str]) -> str:
        """Calculate risk level based on security warnings.

        Args:
            warnings: List of security warnings.

        Returns:
            Risk level string.
        """
        return (
            PluginConstants.DEFAULT_RISK_LEVEL
            if warnings
            else PluginConstants.LOW_RISK_LEVEL
        )

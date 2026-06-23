class RSCError(Exception):
    """Base class for RSC errors."""


class StateLoadError(RSCError):
    """Raised when state files cannot be parsed."""


class ArtifactParseError(RSCError):
    """Raised when artifact markers are malformed."""


class ConfigurationError(RSCError):
    """Raised when runtime configuration is invalid."""

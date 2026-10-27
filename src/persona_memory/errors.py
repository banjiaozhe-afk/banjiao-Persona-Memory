class PersonaMemoryError(Exception):
    """Base class for expected application errors."""


class ValidationError(PersonaMemoryError):
    """Raised when user-supplied data is invalid."""


class ConfigurationError(PersonaMemoryError):
    """Raised when persona configuration is invalid."""


class SensitiveContentError(ValidationError):
    """Raised when content appears to contain credentials or private data."""


class MemoryNotFoundError(PersonaMemoryError):
    """Raised when a requested memory does not exist."""


class DuplicateMemoryError(PersonaMemoryError):
    """Raised when the same subject already has an identical memory."""


class ContextBudgetError(PersonaMemoryError):
    """Raised when required persona and current input exceed the budget."""

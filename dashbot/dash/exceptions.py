class DashApiError(Exception):
    """Raised when the Dash API returns an error response."""


class DashAuthError(DashApiError):
    """Raised when the configured API key is missing, invalid, or expired."""

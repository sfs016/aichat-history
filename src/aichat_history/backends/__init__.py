"""Auto-detect installed IDE backends and provide a unified registry."""

from ..provider import ChatProvider
from .cursor import CursorProvider


def get_available_providers() -> list[ChatProvider]:
    """Auto-detect which IDEs are installed and return their providers."""
    providers = []
    for ProviderClass in [CursorProvider]:
        try:
            provider = ProviderClass()
            if provider.is_available():
                providers.append(provider)
        except Exception:
            continue
    return providers

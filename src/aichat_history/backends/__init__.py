"""Auto-detect installed IDE backends and provide a unified registry."""

from ..provider import ChatProvider
from .claude_code import ClaudeCodeProvider
from .cursor import CursorProvider
from .opencode import OpenCodeProvider


def get_available_providers() -> list[ChatProvider]:
    """Auto-detect which IDEs are installed and return their providers."""
    providers = []
    for ProviderClass in [CursorProvider, ClaudeCodeProvider, OpenCodeProvider]:
        try:
            provider = ProviderClass()
            if provider.is_available():
                providers.append(provider)
        except Exception:
            continue
    return providers

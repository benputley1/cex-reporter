"""Slack bot module for conversational AI interface"""

# Try to import bot components
# Slack dependencies are optional, so we handle import errors gracefully
try:
    from .slack_bot import AlkimiBot, create_bot
    __all__ = ['AlkimiBot', 'create_bot']
except ImportError as e:
    # Slack dependencies not installed
    import warnings
    warnings.warn(f"Slack bot components not available: {e}")
    __all__ = []

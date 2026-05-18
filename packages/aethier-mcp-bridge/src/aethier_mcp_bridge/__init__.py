"""aethier-mcp host bridge."""
from .server import DEFAULT_HOST, DEFAULT_PORT, main, serve

__version__ = "0.1.0"
__all__ = ["serve", "main", "DEFAULT_HOST", "DEFAULT_PORT", "__version__"]

"""aethier-mcp shared infrastructure: bridge client + MCP bootstrap."""
from . import host, toollog
from .server import create_server, run
from .toollog import add_log_fields

__version__ = "0.1.0"
__all__ = [
    "host", "toollog", "create_server", "run",
    "add_log_fields", "__version__",
]

"""
opinionated_mcp: Zero-config OAuth for MCP servers

Opinionated decisions:
- Google OAuth only
- Fernet-encrypted user ID cookies
- Automatic auth redirects
- PKCE with no client secrets
- FastAPI + FastMCP integration
"""

import importlib.metadata

from .server import OpinionatedMCP
from .crypto import generate_session_key

__version__ = importlib.metadata.version(__name__)
__all__ = ["OpinionatedMCP", "generate_session_key"]

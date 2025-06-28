"""
Example MCP server using OpinionatedMCP with user-aware tools
"""

from typing import Optional
from ..server import OpinionatedMCP
from ..crypto import generate_session_key

__all__ = ["ExampleMCPServer", "create_example_server"]

# In-memory storage for user data (use a database in production)
user_data = {}

# Simple user session tracking (in production, this would be more sophisticated)
current_user_session: Optional[str] = None


class ExampleMCPServer:
    """Example MCP server with user-aware MCP tools"""

    def __init__(self, google_client_id: str, base_url: str):
        self.google_client_id = google_client_id
        self.base_url = base_url
        self.session_key = generate_session_key()

        self.server = OpinionatedMCP(
            name="Example MCP Server",
            google_client_id=self.google_client_id,
            session_key=self.session_key,
            base_url=self.base_url,
        )

        self._setup_tools()

    def _setup_tools(self):
        """Setup MCP tools that are user-aware"""

        @self.server.authenticated_tool(
            name="write_name", description="Store your name"
        )
        def write_name(user_id: str, name: str) -> str:
            """Store the user's name. User ID is automatically provided."""
            user_data[user_id] = name
            return f"Stored name '{name}' for user {user_id}"

        @self.server.authenticated_tool(
            name="read_name", description="Get your stored name"
        )
        def read_name(user_id: str) -> str:
            """Retrieve the user's stored name. User ID is automatically provided."""
            name = user_data.get(user_id, "No name stored")
            return f"Your stored name is: {name}"

        # Store references for testing
        self._write_name = write_name
        self._read_name = read_name


def create_example_server(google_client_id: str, base_url: str) -> ExampleMCPServer:
    """Factory function to create an example MCP server"""
    return ExampleMCPServer(google_client_id, base_url)

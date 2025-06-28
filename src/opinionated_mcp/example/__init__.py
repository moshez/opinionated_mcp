"""
Example MCP server using OpinionatedMCP
"""

from fastapi import Request, HTTPException
from ..server import OpinionatedMCP
from ..crypto import generate_session_key

__all__ = ["ExampleMCPServer", "create_example_server"]


class ExampleMCPServer:
    """Example MCP server with basic tools and authenticated endpoints"""

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
        self._setup_endpoints()

    def _setup_tools(self):
        """Setup MCP tools"""

        @self.server.tool(name="echo", description="Echo back the input text")
        def echo_tool(text: str) -> str:
            """Simple echo tool that returns the input text"""
            return f"Echo: {text}"

        @self.server.tool(name="add", description="Add two numbers")
        def add_tool(a: int, b: int) -> int:
            """Add two integers and return the result"""
            return a + b

        # Store references for testing
        self._echo_tool = echo_tool
        self._add_tool = add_tool

    def _setup_endpoints(self):
        """Setup authenticated endpoints"""

        @self.server.app.get("/profile")
        async def profile(request: Request):
            """Get user profile information"""
            user_id = self.server.oauth_handler.get_user_from_request(request)
            if not user_id:
                raise HTTPException(status_code=401, detail="Authentication required")
            return {
                "user_id": user_id,
                "profile": "User profile data",
                "authenticated": True,
            }

        @self.server.app.get("/data")
        async def get_user_data(request: Request):
            """Get user-specific data"""
            user_id = self.server.oauth_handler.get_user_from_request(request)
            if not user_id:
                raise HTTPException(status_code=401, detail="Authentication required")
            return {"user_id": user_id, "data": "User-specific data"}

        @self.server.app.post("/data")
        async def post_user_data(request: Request):
            """Update user-specific data"""
            user_id = self.server.oauth_handler.get_user_from_request(request)
            if not user_id:
                raise HTTPException(status_code=401, detail="Authentication required")
            return {"user_id": user_id, "message": "Data updated successfully"}


def create_example_server(google_client_id: str, base_url: str) -> ExampleMCPServer:
    """Factory function to create an example MCP server"""
    return ExampleMCPServer(google_client_id, base_url)

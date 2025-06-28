"""FastAPI route definitions for OpinionatedMCP"""

from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from .auth import GoogleOAuthHandler


def setup_routes(app, oauth_handler: GoogleOAuthHandler, name: str, base_url: str):
    """Setup OAuth and utility routes for the FastAPI app"""

    @app.get("/")
    async def home():
        return {
            "message": f"{name} MCP Server",
            "login": "/login",
            "mcp_endpoint": "/mcp",
        }

    @app.get("/login")
    async def login(request: Request):
        """Start Google OAuth flow"""
        auth_url = oauth_handler.generate_auth_url(request)
        return RedirectResponse(url=auth_url)

    @app.get("/callback")
    async def callback(
        request: Request,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Handle Google OAuth callback"""
        if error:
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state")

        user_email = await oauth_handler.handle_callback(request, code, state)

        return {
            "message": "Successfully authenticated!",
            "user": user_email,
            "mcp_endpoint": "/mcp",
        }

    @app.get("/user")
    async def current_user(request: Request):
        """Get current authenticated user"""
        if not request.session.get("authenticated"):
            raise HTTPException(status_code=401, detail="Not authenticated")

        user_id = oauth_handler.get_user_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid session")

        return {"user_id": user_id, "authenticated": True}

    @app.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return {"message": "Logged out"}

    @app.get("/.well-known/oauth-authorization-server")
    async def oauth_metadata():
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url.rstrip('/')}/login",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
        }

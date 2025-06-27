"""Main OpinionatedMCP server class"""

import uvicorn
import contextlib
from typing import Optional
from dataclasses import dataclass
from functools import wraps
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from mcp.server.fastmcp import FastMCP

from .crypto import SessionCrypto
from .auth import GoogleOAuthHandler
from .routes import setup_routes


@dataclass
class OpinionatedMCP:
    """Zero-config OAuth MCP server with Google auth"""
    
    name: str
    google_client_id: str
    session_key: str
    base_url: str
    host: str = "localhost"
    port: int = 8000
    
    def __post_init__(self):
        """Initialize complex objects after dataclass creation"""
        self.crypto = SessionCrypto(self.session_key)
        
        self.app = FastAPI(title=f"{self.name} MCP Server")
        self.app.add_middleware(SessionMiddleware, secret_key=self.session_key)
        
        self.mcp = FastMCP(self.name)
        
        self.oauth_handler = GoogleOAuthHandler(
            client_id=self.google_client_id,
            redirect_uri=self.redirect_uri,
            crypto=self.crypto
        )
        
        setup_routes(self.app, self.oauth_handler, self.name, self.base_url)
    
    @property
    def redirect_uri(self) -> str:
        """Generate redirect URI from base URL"""
        return f"{self.base_url.rstrip('/')}/callback"
    
    def reset_session_key(self, new_session_key: str):
        """Rotate the session key (invalidates all existing sessions)"""
        self.session_key = new_session_key
        self.crypto.update_key(new_session_key)
        
        for middleware in self.app.user_middleware:
            if isinstance(middleware.cls, type) and issubclass(middleware.cls, SessionMiddleware):
                middleware.kwargs["secret_key"] = new_session_key
    
    def require_auth(self, func):
        """Decorator to require authentication for MCP tools"""
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user_id = self.oauth_handler.get_user_from_request(request)
            if not user_id:
                raise HTTPException(status_code=401, detail="Authentication required")
            return await func(request, user_id, *args, **kwargs)
        return wrapper
    
    def tool(self, **kwargs):
        """Register an MCP tool (proxies to FastMCP)"""
        return self.mcp.tool(**kwargs)
    
    def authenticated_endpoint(self, path: str, methods: list = ["GET"]):
        """Create an authenticated FastAPI endpoint that receives user_id"""
        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                user_id = self.oauth_handler.get_user_from_request(request)
                if not user_id:
                    raise HTTPException(status_code=401, detail="Authentication required")
                return await func(request, user_id, *args, **kwargs)
            
            for method in methods:
                self.app.add_api_route(path, wrapper, methods=[method])
            
            return wrapper
        return decorator
    
    def run(self, **kwargs):
        """Run the server"""
        @contextlib.asynccontextmanager
        async def lifespan(app: FastAPI):
            async with self.mcp.session_manager.run():
                yield
        
        self.app.router.lifespan_context = lifespan
        self.app.mount("/mcp", self.mcp.streamable_http_app())
        
        print(f"🚀 Starting {self.name}")
        print(f"📡 Server: http://{self.host}:{self.port}")
        print(f"🔗 Base URL: {self.base_url}")
        print(f"🔐 Login: {self.base_url.rstrip('/')}/login")
        print(f"🤖 MCP: {self.base_url.rstrip('/')}/mcp")
        
        uvicorn.run(self.app, host=self.host, port=self.port, **kwargs)
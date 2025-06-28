"""Main OpinionatedMCP server class"""

import uvicorn
import contextlib
import logging
from dataclasses import dataclass
from functools import wraps
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from mcp.server.fastmcp import FastMCP

from .crypto import SessionCrypto
from .auth import GoogleOAuthHandler
from .routes import setup_routes

logger = logging.getLogger(__name__)


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
            crypto=self.crypto,
        )

        setup_routes(self.app, self.oauth_handler, self.name, self.base_url)

    @property
    def redirect_uri(self) -> str:
        """Generate redirect URI from base URL"""
        return f"{self.base_url.rstrip('/')}/callback"

    def _is_session_middleware(self, middleware) -> bool:
        """Check if middleware is a SessionMiddleware"""
        return isinstance(middleware.cls, type) and issubclass(
            middleware.cls, SessionMiddleware
        )

    def reset_session_key(self, new_session_key: str):
        """Rotate the session key (invalidates all existing sessions)"""
        self.session_key = new_session_key
        self.crypto.update_key(new_session_key)

        for middleware in self.app.user_middleware:
            if self._is_session_middleware(middleware):
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
                    raise HTTPException(
                        status_code=401, detail="Authentication required"
                    )
                return await func(request, user_id, *args, **kwargs)

            for method in methods:
                self.app.add_api_route(path, wrapper, methods=[method])

            return wrapper

        return decorator

    @contextlib.asynccontextmanager
    async def _create_lifespan_context(self, app: FastAPI):
        """Create lifespan context manager for MCP session management"""
        async with self.mcp.session_manager.run():
            yield

    def _setup_server(self):
        """Setup server configuration before running"""
        self.app.router.lifespan_context = self._create_lifespan_context
        self.app.mount("/mcp", self.mcp.streamable_http_app())

    def _log_startup_info(self):
        """Log server startup information"""
        logger.info("🚀 Starting %s", self.name)
        logger.info("📡 Server: http://%s:%s", self.host, self.port)
        logger.info("🔗 Base URL: %s", self.base_url)
        logger.info("🔐 Login: %s/login", self.base_url.rstrip("/"))
        logger.info("🤖 MCP: %s/mcp", self.base_url.rstrip("/"))

    def run(self, **kwargs):
        """Run the server"""
        self._setup_server()
        self._log_startup_info()
        uvicorn.run(self.app, host=self.host, port=self.port, **kwargs)

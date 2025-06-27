"""
opinionated_mcp: Zero-config OAuth for MCP servers

Opinionated decisions:
- Google OAuth only
- Fernet-encrypted user ID cookies
- Automatic auth redirects
- PKCE with no client secrets
- FastAPI + FastMCP integration
"""

import secrets
import httpx
import uvicorn
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass, field
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from mcp.server.fastmcp import FastMCP
import contextlib
from datetime import datetime
import base64
import hashlib
from cryptography.fernet import Fernet
from functools import wraps
# Removed contextvars - we pass user_id explicitly

# We'll pass user_id directly to functions instead of using context variables

def generate_session_key() -> str:
    """Generate a session key for Fernet encryption"""
    return Fernet.generate_key().decode()

@dataclass
class OpinionatedMCP:
    """Zero-config OAuth MCP server with Google auth"""
    
    name: str
    google_client_id: str
    session_key: str
    base_url: str
    host: str = "localhost"
    port: int = 8000
    
    # These will be initialized in __post_init__
    fernet: Fernet = field(init=False)
    app: FastAPI = field(init=False)
    mcp: FastMCP = field(init=False)
    
    def __post_init__(self):
        """Initialize complex objects after dataclass creation"""
        self.fernet = Fernet(self.session_key.encode())
        
        # Setup FastAPI app
        self.app = FastAPI(title=f"{self.name} MCP Server")
        self.app.add_middleware(SessionMiddleware, secret_key=self.session_key)
        
        # Setup MCP server without auth - we handle it ourselves
        self.mcp = FastMCP(self.name)
        
        # Setup routes
        self._setup_routes()
    
    @property
    def redirect_uri(self) -> str:
        """Generate redirect URI from base URL"""
        return f"{self.base_url.rstrip('/')}/callback"
    
    def reset_session_key(self, new_session_key: str):
        """Rotate the session key (invalidates all existing sessions)"""
        self.session_key = new_session_key
        self.fernet = Fernet(new_session_key.encode())
        
        # Update middleware (note: this might require app restart in some deployments)
        for middleware in self.app.user_middleware:
            if isinstance(middleware.cls, type) and issubclass(middleware.cls, SessionMiddleware):
                middleware.kwargs["secret_key"] = new_session_key
    
    def require_auth(self, func):
        """Decorator to require authentication for MCP tools"""
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user_id = await self._get_user_from_request(request)
            if not user_id:
                raise HTTPException(status_code=401, detail="Authentication required")
            # Call the original function with request and user_id
            return await func(request, user_id, *args, **kwargs)
        return wrapper
    
    async def _get_user_from_request(self, request: Request) -> Optional[str]:
        """Extract and decrypt user ID from request session"""
        if not request.session.get("authenticated"):
            return None
        
        encrypted_user_id = request.session.get("user_id")
        if not encrypted_user_id:
            return None
        
        try:
            return self.fernet.decrypt(encrypted_user_id.encode()).decode()
        except Exception:
            return None
    
    def _setup_routes(self):
        """Setup OAuth and utility routes"""
        
        @self.app.get("/")
        async def home():
            return {
                "message": f"{self.name} MCP Server",
                "login": "/login",
                "mcp_endpoint": "/mcp"
            }
        
        @self.app.get("/login")
        async def login(request: Request):
            """Start Google OAuth flow"""
            state = secrets.token_urlsafe(32)
            code_verifier = self._generate_code_verifier()
            code_challenge = self._generate_code_challenge(code_verifier)
            
            request.session["oauth_state"] = state
            request.session["code_verifier"] = code_verifier
            
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?client_id={self.google_client_id}"
                f"&redirect_uri={self.redirect_uri}"
                f"&scope=openid email profile"
                f"&response_type=code"
                f"&state={state}"
                f"&code_challenge={code_challenge}"
                f"&code_challenge_method=S256"
            )
            
            return RedirectResponse(url=auth_url)
        
        @self.app.get("/callback")
        async def callback(request: Request, code: str = None, state: str = None, error: str = None):
            """Handle Google OAuth callback"""
            if error:
                raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
            
            if not code or not state:
                raise HTTPException(status_code=400, detail="Missing code or state")
            
            # Verify state
            if request.session.get("oauth_state") != state:
                raise HTTPException(status_code=400, detail="Invalid state")
            
            code_verifier = request.session.get("code_verifier")
            if not code_verifier:
                raise HTTPException(status_code=400, detail="Missing code verifier")
            
            # Exchange code for token
            user_email = await self._exchange_code_for_user(code, code_verifier)
            
            # Create encrypted cookie
            encrypted_user_id = self.fernet.encrypt(user_email.encode()).decode()
            
            # Store in session and return success
            request.session["user_id"] = encrypted_user_id
            request.session["authenticated"] = True
            
            return {
                "message": "Successfully authenticated!",
                "user": user_email,
                "mcp_endpoint": "/mcp"
            }
        
        @self.app.get("/user")
        async def current_user(request: Request):
            """Get current authenticated user"""
            # For the web interface, we still check the session directly
            if not request.session.get("authenticated"):
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            encrypted_user_id = request.session.get("user_id")
            if not encrypted_user_id:
                raise HTTPException(status_code=401, detail="No user session")
            
            try:
                user_id = self.fernet.decrypt(encrypted_user_id.encode()).decode()
                return {"user_id": user_id, "authenticated": True}
            except Exception:
                raise HTTPException(status_code=401, detail="Invalid session")
        
        @self.app.post("/logout")
        async def logout(request: Request):
            request.session.clear()
            return {"message": "Logged out"}
        
        @self.app.get("/.well-known/oauth-authorization-server")
        async def oauth_metadata():
            return {
                "issuer": self.base_url,
                "authorization_endpoint": f"{self.base_url.rstrip('/')}/login",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "code_challenge_methods_supported": ["S256"]
            }
    
    async def _exchange_code_for_user(self, code: str, code_verifier: str) -> str:
        """Exchange OAuth code for user email"""
        async with httpx.AsyncClient() as client:
            # Get access token
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.google_client_id,
                    "code": code,
                    "code_verifier": code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if token_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Token exchange failed")
            
            access_token = token_response.json()["access_token"]
            
            # Get user info
            user_response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
            )
            
            if user_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            return user_response.json()["email"]
    
    def _generate_code_verifier(self):
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    def _generate_code_challenge(self, verifier):
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    
    def tool(self, **kwargs):
        """Register an MCP tool (proxies to FastMCP)"""
        return self.mcp.tool(**kwargs)
    
    def authenticated_endpoint(self, path: str, methods: list = ["GET"]):
        """Create an authenticated FastAPI endpoint that receives user_id"""
        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                user_id = await self._get_user_from_request(request)
                if not user_id:
                    raise HTTPException(status_code=401, detail="Authentication required")
                return await func(request, user_id, *args, **kwargs)
            
            # Register with FastAPI
            for method in methods:
                self.app.add_api_route(path, wrapper, methods=[method])
            
            return wrapper
        return decorator
    
    def run(self, **kwargs):
        """Run the server"""
        
        # Setup MCP integration
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
        
        uvicorn.run(self.app, host=self.host, port=self.port, **kwargs)s
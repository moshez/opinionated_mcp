"""Tests for routes module"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from hamcrest import assert_that, is_, contains_string, has_key
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from opinionated_mcp.routes import setup_routes


class TestSetupRoutes(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
        
        self.mock_oauth_handler = Mock()
        self.mock_oauth_handler.generate_auth_url = Mock(return_value="https://accounts.google.com/oauth")
        self.mock_oauth_handler.handle_callback = AsyncMock(return_value="test@example.com")
        self.mock_oauth_handler.get_user_from_request = Mock(return_value="test@example.com")
        
        setup_routes(self.app, self.mock_oauth_handler, "Test Server", "http://localhost:8000")
        self.client = TestClient(self.app)
    
    def test_home_route(self):
        response = self.client.get("/")
        assert_that(response.status_code, is_(200))
        data = response.json()
        assert_that(data["message"], is_("Test Server MCP Server"))
        assert_that(data["login"], is_("/login"))
        assert_that(data["mcp_endpoint"], is_("/mcp"))
    
    def test_login_route(self):
        response = self.client.get("/login", follow_redirects=False)
        assert_that(response.status_code, is_(307))  # FastAPI redirect response
        self.mock_oauth_handler.generate_auth_url.assert_called_once()
    
    def test_callback_route_with_error(self):
        response = self.client.get("/callback?error=access_denied")
        assert_that(response.status_code, is_(400))
        assert_that(response.json(), has_key("detail"))
        assert_that(response.json()["detail"], contains_string("OAuth error: access_denied"))
    
    def test_callback_route_missing_code(self):
        response = self.client.get("/callback?state=test_state")
        assert_that(response.status_code, is_(400))
        assert_that(response.json(), has_key("detail"))
        assert_that(response.json()["detail"], contains_string("Missing code or state"))
    
    def test_callback_route_missing_state(self):
        response = self.client.get("/callback?code=test_code")
        assert_that(response.status_code, is_(400))
        assert_that(response.json(), has_key("detail"))
        assert_that(response.json()["detail"], contains_string("Missing code or state"))
    
    def test_callback_route_success(self):
        response = self.client.get("/callback?code=test_code&state=test_state")
        assert_that(response.status_code, is_(200))
        data = response.json()
        assert_that(data["message"], is_("Successfully authenticated!"))
        assert_that(data["user"], is_("test@example.com"))
        assert_that(data["mcp_endpoint"], is_("/mcp"))
        self.mock_oauth_handler.handle_callback.assert_called_once()
    
    def test_current_user_route_authenticated(self):
        # Override the mock to simulate authenticated session
        def mock_session_get(key):
            if key == "authenticated":
                return True
            return None
        
        with patch('fastapi.Request') as mock_request_class:
            mock_request = mock_request_class.return_value
            mock_request.session.get = mock_session_get
            
            # Directly test the route function
            from opinionated_mcp.routes import setup_routes
            app = FastAPI()
            app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
            setup_routes(app, self.mock_oauth_handler, "Test Server", "http://localhost:8000")
            
            # Find the current_user route function
            for route in app.routes:
                if hasattr(route, 'path') and route.path == "/user":
                    import asyncio
                    result = asyncio.run(route.endpoint(mock_request))
                    assert_that(result["user_id"], is_("test@example.com"))
                    assert_that(result["authenticated"], is_(True))
                    break
    
    def test_current_user_route_not_authenticated(self):
        response = self.client.get("/user")
        assert_that(response.status_code, is_(401))
        assert_that(response.json(), has_key("detail"))
        assert_that(response.json()["detail"], contains_string("Not authenticated"))
    
    def test_current_user_route_invalid_session(self):
        # Override the mock to simulate authenticated session but invalid user
        def mock_session_get(key):
            if key == "authenticated":
                return True
            return None
        
        # Create handler that returns None for get_user_from_request
        mock_oauth_handler_invalid = Mock()
        mock_oauth_handler_invalid.get_user_from_request = Mock(return_value=None)
        
        with patch('fastapi.Request') as mock_request_class:
            mock_request = mock_request_class.return_value
            mock_request.session.get = mock_session_get
            
            # Directly test the route function
            app = FastAPI()
            app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
            setup_routes(app, mock_oauth_handler_invalid, "Test Server", "http://localhost:8000")
            
            # Find the current_user route function
            for route in app.routes:
                if hasattr(route, 'path') and route.path == "/user":
                    with self.assertRaises(HTTPException) as context:
                        import asyncio
                        asyncio.run(route.endpoint(mock_request))
                    
                    assert_that(context.exception.status_code, is_(401))
                    assert_that(str(context.exception.detail), contains_string("Invalid session"))
                    break
    
    def test_logout_route(self):
        response = self.client.post("/logout")
        assert_that(response.status_code, is_(200))
        assert_that(response.json()["message"], is_("Logged out"))
    
    def test_oauth_metadata_route(self):
        response = self.client.get("/.well-known/oauth-authorization-server")
        assert_that(response.status_code, is_(200))
        data = response.json()
        assert_that(data["issuer"], is_("http://localhost:8000"))
        assert_that(data["authorization_endpoint"], is_("http://localhost:8000/login"))
        assert_that(data, has_key("response_types_supported"))
        assert_that(data, has_key("grant_types_supported"))
        assert_that(data, has_key("code_challenge_methods_supported"))
        assert_that("code" in data["response_types_supported"], is_(True))
        assert_that("authorization_code" in data["grant_types_supported"], is_(True))
        assert_that("S256" in data["code_challenge_methods_supported"], is_(True))
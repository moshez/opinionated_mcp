"""Tests for server module"""

import unittest
import logging
from unittest.mock import Mock
from hamcrest import assert_that, is_, not_, instance_of, has_property, contains_string
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from opinionated_mcp.server import OpinionatedMCP
from opinionated_mcp.crypto import generate_session_key


class LogCapture:
    """Capture log messages for testing"""

    def __init__(self):
        self.records = []
        self.handler = logging.Handler()
        self.handler.emit = lambda record: self.records.append(record)

    def setup(self, logger_name):
        """Setup log capture for a specific logger"""
        logger = logging.getLogger(logger_name)
        logger.addHandler(self.handler)
        logger.setLevel(logging.INFO)
        return logger

    def get_messages(self):
        """Get all captured log messages"""
        return [record.getMessage() for record in self.records]

    def clear(self):
        """Clear captured messages"""
        self.records.clear()


class TestOpinionatedMCP(unittest.TestCase):
    def setUp(self):
        self.server_config = {
            "name": "Test MCP Server",
            "google_client_id": "test_client_id",
            "session_key": generate_session_key(),
            "base_url": "http://localhost:8000",
            "host": "localhost",
            "port": 8000,
        }

    def test_init(self):
        server = OpinionatedMCP(**self.server_config)

        assert_that(server.name, is_("Test MCP Server"))
        assert_that(server.google_client_id, is_("test_client_id"))
        assert_that(server.base_url, is_("http://localhost:8000"))
        assert_that(server.host, is_("localhost"))
        assert_that(server.port, is_(8000))

        assert_that(server, has_property("crypto"))
        assert_that(server, has_property("app"))
        assert_that(server, has_property("mcp"))
        assert_that(server, has_property("oauth_handler"))

        assert_that(server.app, instance_of(FastAPI))

    def test_redirect_uri(self):
        server = OpinionatedMCP(**self.server_config)
        assert_that(server.redirect_uri, is_("http://localhost:8000/callback"))

    def test_redirect_uri_trailing_slash(self):
        config = self.server_config.copy()
        config["base_url"] = "http://localhost:8000/"
        server = OpinionatedMCP(**config)
        assert_that(server.redirect_uri, is_("http://localhost:8000/callback"))

    def test_reset_session_key(self):
        server = OpinionatedMCP(**self.server_config)
        old_key = server.session_key
        new_key = generate_session_key()

        server.reset_session_key(new_key)

        assert_that(server.session_key, is_(new_key))
        assert_that(server.session_key, not_(is_(old_key)))

    def test_is_session_middleware_true(self):
        server = OpinionatedMCP(**self.server_config)

        class MockMiddleware:
            def __init__(self):
                self.cls = SessionMiddleware

        mock_middleware = MockMiddleware()
        result = server._is_session_middleware(mock_middleware)
        assert_that(result, is_(True))

    def test_is_session_middleware_false(self):
        server = OpinionatedMCP(**self.server_config)

        class MockMiddleware:
            def __init__(self):
                self.cls = str  # Not SessionMiddleware

        mock_middleware = MockMiddleware()
        result = server._is_session_middleware(mock_middleware)
        assert_that(result, is_(False))

    def test_reset_session_key_with_middleware(self):
        server = OpinionatedMCP(**self.server_config)

        # Create a real SessionMiddleware-like object
        class MockMiddleware:
            def __init__(self):
                self.cls = SessionMiddleware
                self.kwargs = {"secret_key": "old_key"}

        mock_middleware = MockMiddleware()
        server.app.user_middleware = [mock_middleware]

        new_key = generate_session_key()
        server.reset_session_key(new_key)

        assert_that(server.session_key, is_(new_key))
        assert_that(mock_middleware.kwargs["secret_key"], is_(new_key))

    def test_reset_session_key_with_mixed_middleware(self):
        server = OpinionatedMCP(**self.server_config)

        # Create both SessionMiddleware and non-SessionMiddleware objects
        class SessionMiddlewareObj:
            def __init__(self):
                self.cls = SessionMiddleware
                self.kwargs = {"secret_key": "old_key"}

        class OtherMiddlewareObj:
            def __init__(self):
                self.cls = str  # Not SessionMiddleware
                self.kwargs = {"some_key": "some_value"}

        session_middleware = SessionMiddlewareObj()
        other_middleware = OtherMiddlewareObj()
        server.app.user_middleware = [session_middleware, other_middleware]

        new_key = generate_session_key()
        server.reset_session_key(new_key)

        # SessionMiddleware should be updated
        assert_that(session_middleware.kwargs["secret_key"], is_(new_key))
        # Other middleware should not be affected
        assert_that(other_middleware.kwargs["some_key"], is_("some_value"))

    def test_home_endpoint(self):
        """Test the home endpoint through HTTP"""
        server = OpinionatedMCP(**self.server_config)

        with TestClient(server.app) as client:
            response = client.get("/")
            assert_that(response.status_code, is_(200))
            data = response.json()
            assert_that(data["message"], is_("Test MCP Server MCP Server"))
            assert_that(data["login"], is_("/login"))
            assert_that(data["mcp_endpoint"], is_("/mcp"))

    def test_login_endpoint_redirects(self):
        """Test the login endpoint redirects to Google OAuth"""
        server = OpinionatedMCP(**self.server_config)

        with TestClient(server.app) as client:
            response = client.get("/login", follow_redirects=False)
            assert_that(response.status_code, is_(307))
            # Should redirect to Google OAuth
            assert_that(
                response.headers["location"], contains_string("accounts.google.com")
            )

    def test_user_endpoint_not_authenticated(self):
        """Test the user endpoint when not authenticated"""
        server = OpinionatedMCP(**self.server_config)

        with TestClient(server.app) as client:
            response = client.get("/user")
            assert_that(response.status_code, is_(401))
            assert_that(response.json()["detail"], contains_string("Not authenticated"))

    def test_logout_endpoint(self):
        """Test the logout endpoint"""
        server = OpinionatedMCP(**self.server_config)

        with TestClient(server.app) as client:
            response = client.post("/logout")
            assert_that(response.status_code, is_(200))
            assert_that(response.json()["message"], is_("Logged out"))

    def test_oauth_metadata_endpoint(self):
        """Test OAuth metadata endpoint"""
        server = OpinionatedMCP(**self.server_config)

        with TestClient(server.app) as client:
            response = client.get("/.well-known/oauth-authorization-server")
            assert_that(response.status_code, is_(200))
            data = response.json()
            assert_that(data["issuer"], is_("http://localhost:8000"))
            assert_that(
                data["authorization_endpoint"], is_("http://localhost:8000/login")
            )

    def test_tool_method(self):
        """Test tool method delegates to mcp.tool"""
        server = OpinionatedMCP(**self.server_config)

        # Test that the tool method delegates to mcp.tool
        original_tool = server.mcp.tool
        called_with = None

        def capture_call(**kwargs):
            nonlocal called_with
            called_with = kwargs
            return original_tool(**kwargs)

        server.mcp.tool = capture_call

        try:
            server.tool(name="test_tool")
            assert_that(called_with, is_({"name": "test_tool"}))
        finally:
            server.mcp.tool = original_tool

    def test_log_startup_info(self):
        """Test startup logging captures expected messages"""
        log_capture = LogCapture()
        log_capture.setup("opinionated_mcp.server")

        try:
            server = OpinionatedMCP(**self.server_config)
            server._log_startup_info()

            messages = log_capture.get_messages()
            assert_that(len(messages), is_(5))

            # Check log messages contain expected content
            assert_that(messages[0], contains_string("Starting"))
            assert_that(messages[0], contains_string("Test MCP Server"))

            assert_that(messages[1], contains_string("Server:"))
            assert_that(messages[1], contains_string("localhost"))
            assert_that(messages[1], contains_string("8000"))

            assert_that(messages[2], contains_string("Base URL"))
            assert_that(messages[2], contains_string("http://localhost:8000"))

            assert_that(messages[3], contains_string("Login"))
            assert_that(messages[4], contains_string("MCP"))
        finally:
            log_capture.clear()

    def test_setup_server(self):
        """Test server setup configures lifespan and mounts MCP"""
        server = OpinionatedMCP(**self.server_config)

        # Before setup
        original_lifespan = server.app.router.lifespan_context

        server._setup_server()

        # After setup, lifespan should be configured
        assert_that(server.app.router.lifespan_context, is_(not_(original_lifespan)))
        assert_that(server.app.router.lifespan_context, is_(not_(None)))

        # Check that MCP is mounted (would be in routes)
        routes = [route for route in server.app.routes if hasattr(route, "path")]
        mcp_routes = [route for route in routes if route.path.startswith("/mcp")]
        assert_that(len(mcp_routes), is_(not_(0)))

    def test_create_lifespan_context_runs(self):
        """Test lifespan context manager can be executed"""
        server = OpinionatedMCP(**self.server_config)

        # Need to initialize session manager first by calling streamable_http_app
        server.mcp.streamable_http_app()

        async def test_lifespan_execution():
            # Test that the lifespan context manager works without errors
            async with server._create_lifespan_context(server.app):
                # Context manager should work without issues
                pass

        import asyncio

        # This should complete without raising exceptions
        asyncio.run(test_lifespan_execution())

    def test_run_method(self):
        """Test run method calls setup and logging"""
        server = OpinionatedMCP(**self.server_config)

        # Track method calls
        setup_called = False
        log_called = False
        uvicorn_called = False
        uvicorn_args = None

        original_setup = server._setup_server
        original_log = server._log_startup_info

        def capture_setup():
            nonlocal setup_called
            setup_called = True
            return original_setup()

        def capture_log():
            nonlocal log_called
            log_called = True
            return original_log()

        def capture_uvicorn_run(app, **kwargs):
            nonlocal uvicorn_called, uvicorn_args
            uvicorn_called = True
            uvicorn_args = kwargs

        server._setup_server = capture_setup
        server._log_startup_info = capture_log

        # Mock uvicorn.run to avoid actually starting server
        import opinionated_mcp.server

        original_uvicorn_run = opinionated_mcp.server.uvicorn.run
        opinionated_mcp.server.uvicorn.run = capture_uvicorn_run

        try:
            server.run(debug=True)

            assert_that(setup_called, is_(True))
            assert_that(log_called, is_(True))
            assert_that(uvicorn_called, is_(True))
            assert_that(uvicorn_args["host"], is_("localhost"))
            assert_that(uvicorn_args["port"], is_(8000))
            assert_that(uvicorn_args["debug"], is_(True))
        finally:
            # Restore original methods
            server._setup_server = original_setup
            server._log_startup_info = original_log
            opinionated_mcp.server.uvicorn.run = original_uvicorn_run

    def test_require_auth_decorator_authenticated(self):
        """Test require_auth decorator with authenticated user"""
        server = OpinionatedMCP(**self.server_config)

        @server.require_auth
        async def test_func(request, user_id):
            return f"Hello {user_id}"

        # Create a mock request with valid auth
        mock_request = Mock()
        mock_request.session = {
            "authenticated": True,
            "user_id": server.crypto.encrypt_user_id("test@example.com"),
        }

        import asyncio

        result = asyncio.run(test_func(mock_request))
        assert_that(result, is_("Hello test@example.com"))

    def test_require_auth_decorator_not_authenticated(self):
        """Test require_auth decorator with unauthenticated user"""
        server = OpinionatedMCP(**self.server_config)

        @server.require_auth
        async def test_func(request, user_id):
            return f"Hello {user_id}"

        # Create a mock request without auth
        mock_request = Mock()
        mock_request.session = {"authenticated": False}

        with self.assertRaises(HTTPException) as context:
            import asyncio

            asyncio.run(test_func(mock_request))

        assert_that(context.exception.status_code, is_(401))
        assert_that(str(context.exception.detail), is_("Authentication required"))

    def test_authenticated_endpoint_decorator_authenticated(self):
        """Test authenticated_endpoint decorator with authenticated user"""
        server = OpinionatedMCP(**self.server_config)

        @server.authenticated_endpoint("/test", methods=["GET"])
        async def test_endpoint(request, user_id):
            return {"user": user_id}

        # Create a mock request with valid auth
        mock_request = Mock()
        mock_request.session = {
            "authenticated": True,
            "user_id": server.crypto.encrypt_user_id("test@example.com"),
        }

        import asyncio

        result = asyncio.run(test_endpoint(mock_request))
        assert_that(result, is_({"user": "test@example.com"}))

    def test_authenticated_endpoint_decorator_not_authenticated(self):
        """Test authenticated_endpoint decorator with unauthenticated user"""
        server = OpinionatedMCP(**self.server_config)

        @server.authenticated_endpoint("/test", methods=["GET"])
        async def test_endpoint(request, user_id):
            return {"user": user_id}

        # Create a mock request without auth
        mock_request = Mock()
        mock_request.session = {"authenticated": False}

        with self.assertRaises(HTTPException) as context:
            import asyncio

            asyncio.run(test_endpoint(mock_request))

        assert_that(context.exception.status_code, is_(401))
        assert_that(str(context.exception.detail), is_("Authentication required"))

    def test_authenticated_endpoint_decorator_registration(self):
        """Test authenticated_endpoint decorator registers routes properly"""
        server = OpinionatedMCP(**self.server_config)

        routes_before = len(server.app.routes)

        @server.authenticated_endpoint("/test", methods=["GET", "POST"])
        async def test_endpoint(request, user_id):
            return {"user": user_id}

        routes_after = len(server.app.routes)

        # Should have added 2 routes (GET and POST)
        assert_that(routes_after, is_(routes_before + 2))

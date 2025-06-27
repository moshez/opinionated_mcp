"""Tests for server module"""

import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from hamcrest import assert_that, is_, not_, instance_of, has_property
from fastapi import FastAPI, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from opinionated_mcp.server import OpinionatedMCP
from opinionated_mcp.crypto import generate_session_key


class TestOpinionatedMCP(unittest.TestCase):
    def setUp(self):
        self.server_config = {
            "name": "Test MCP Server",
            "google_client_id": "test_client_id",
            "session_key": generate_session_key(),
            "base_url": "http://localhost:8000",
            "host": "localhost",
            "port": 8000
        }
    
    def test_init(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            assert_that(server.name, is_("Test MCP Server"))
            assert_that(server.google_client_id, is_("test_client_id"))
            assert_that(server.base_url, is_("http://localhost:8000"))
            assert_that(server.host, is_("localhost"))
            assert_that(server.port, is_(8000))
            
            assert_that(server, has_property('crypto'))
            assert_that(server, has_property('app'))
            assert_that(server, has_property('mcp'))
            assert_that(server, has_property('oauth_handler'))
            
            assert_that(server.app, instance_of(FastAPI))
    
    def test_redirect_uri(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            assert_that(server.redirect_uri, is_("http://localhost:8000/callback"))
    
    def test_redirect_uri_trailing_slash(self):
        config = self.server_config.copy()
        config["base_url"] = "http://localhost:8000/"
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**config)
            assert_that(server.redirect_uri, is_("http://localhost:8000/callback"))
    
    def test_reset_session_key(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            old_key = server.session_key
            new_key = generate_session_key()
            
            server.reset_session_key(new_key)
            
            assert_that(server.session_key, is_(new_key))
            assert_that(server.session_key, not_(is_(old_key)))
    
    def test_is_session_middleware_true(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            class MockMiddleware:
                def __init__(self):
                    self.cls = SessionMiddleware
            
            mock_middleware = MockMiddleware()
            result = server._is_session_middleware(mock_middleware)
            assert_that(result, is_(True))
    
    def test_is_session_middleware_false(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            class MockMiddleware:
                def __init__(self):
                    self.cls = str  # Not SessionMiddleware
            
            mock_middleware = MockMiddleware()
            result = server._is_session_middleware(mock_middleware)
            assert_that(result, is_(False))
    
    def test_reset_session_key_with_middleware(self):
        with patch('opinionated_mcp.server.setup_routes'):
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
        with patch('opinionated_mcp.server.setup_routes'):
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
    
    def test_require_auth_decorator_authenticated(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            @server.require_auth
            async def test_func(request, user_id):
                return f"Hello {user_id}"
            
            mock_request = Mock()
            
            async def test_authenticated():
                with patch.object(server.oauth_handler, 'get_user_from_request', return_value="test@example.com"):
                    return await test_func(mock_request)
            
            import asyncio
            result = asyncio.run(test_authenticated())
            assert_that(result, is_("Hello test@example.com"))
    
    def test_require_auth_decorator_not_authenticated(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            @server.require_auth
            async def test_func(request, user_id):
                return f"Hello {user_id}"
            
            mock_request = Mock()
            
            async def test_not_authenticated():
                with patch.object(server.oauth_handler, 'get_user_from_request', return_value=None):
                    await test_func(mock_request)
            
            with self.assertRaises(HTTPException) as context:
                import asyncio
                asyncio.run(test_not_authenticated())
            
            assert_that(context.exception.status_code, is_(401))
            assert_that(str(context.exception.detail), is_("Authentication required"))
    
    def test_tool_method(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            with patch.object(server.mcp, 'tool') as mock_tool:
                server.tool(name="test_tool")
                mock_tool.assert_called_once_with(name="test_tool")
    
    def test_authenticated_endpoint_decorator_authenticated(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            @server.authenticated_endpoint("/test", methods=["GET"])
            async def test_endpoint(request, user_id):
                return {"user": user_id}
            
            mock_request = Mock()
            
            async def test_authenticated():
                with patch.object(server.oauth_handler, 'get_user_from_request', return_value="test@example.com"):
                    return await test_endpoint(mock_request)
            
            import asyncio
            result = asyncio.run(test_authenticated())
            assert_that(result, is_({"user": "test@example.com"}))
    
    def test_authenticated_endpoint_decorator_not_authenticated(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            @server.authenticated_endpoint("/test", methods=["GET"])
            async def test_endpoint(request, user_id):
                return {"user": user_id}
            
            mock_request = Mock()
            
            async def test_not_authenticated():
                with patch.object(server.oauth_handler, 'get_user_from_request', return_value=None):
                    await test_endpoint(mock_request)
            
            with self.assertRaises(HTTPException) as context:
                import asyncio
                asyncio.run(test_not_authenticated())
            
            assert_that(context.exception.status_code, is_(401))
            assert_that(str(context.exception.detail), is_("Authentication required"))
    
    def test_authenticated_endpoint_decorator(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            with patch.object(server.app, 'add_api_route') as mock_add_route:
                @server.authenticated_endpoint("/test", methods=["GET", "POST"])
                async def test_endpoint(request, user_id):
                    return {"user": user_id}
                
                assert_that(mock_add_route.call_count, is_(2))
                calls = mock_add_route.call_args_list
                assert_that(calls[0][0][0], is_("/test"))
                assert_that(calls[0][1]["methods"], is_(["GET"]))
                assert_that(calls[1][0][0], is_("/test"))
                assert_that(calls[1][1]["methods"], is_(["POST"]))
    
    def test_setup_server(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            with patch.object(server.app, 'mount') as mock_mount:
                server._setup_server()
                
                mock_mount.assert_called_once()
                assert_that(server.app.router.lifespan_context, is_(not_(None)))
    
    def test_create_lifespan_context(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            async def test_lifespan():
                # Create a mock that simulates the async context manager
                mock_session_manager_run = AsyncMock()
                
                # Patch the mcp object directly with a mock that has the run method
                with patch.object(server, 'mcp') as mock_mcp:
                    mock_mcp.session_manager.run.return_value = mock_session_manager_run
                    
                    # Test the lifespan context manager
                    async with server._create_lifespan_context(server.app):
                        pass
                    
                    mock_mcp.session_manager.run.assert_called_once()
            
            import asyncio
            asyncio.run(test_lifespan())
    
    def test_log_startup_info(self):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            with patch('opinionated_mcp.server.logger') as mock_logger:
                server._log_startup_info()
                
                # Verify all the startup info is logged
                assert_that(mock_logger.info.call_count, is_(5))
                calls = mock_logger.info.call_args_list
                
                # Check that server name, host, port, and URLs are logged
                assert_that(str(calls[0]), contains_string("Test MCP Server"))
                assert_that(str(calls[1]), contains_string("localhost:8000"))
                assert_that(str(calls[2]), contains_string("http://localhost:8000"))
                assert_that(str(calls[3]), contains_string("/login"))
                assert_that(str(calls[4]), contains_string("/mcp"))
    
    @patch('opinionated_mcp.server.uvicorn')
    def test_run(self, mock_uvicorn):
        with patch('opinionated_mcp.server.setup_routes'):
            server = OpinionatedMCP(**self.server_config)
            
            with patch.object(server, '_setup_server') as mock_setup, \
                 patch.object(server, '_log_startup_info') as mock_log:
                server.run(debug=True)
                
                mock_setup.assert_called_once()
                mock_log.assert_called_once()
                mock_uvicorn.run.assert_called_once_with(
                    server.app, 
                    host="localhost", 
                    port=8000, 
                    debug=True
                )
    

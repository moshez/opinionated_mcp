"""Tests for example subpackage"""

import asyncio
import unittest
from unittest.mock import patch
from hamcrest import assert_that, is_, instance_of, has_property
from fastapi.testclient import TestClient
from opinionated_mcp.example import ExampleMCPServer, create_example_server
from opinionated_mcp.server import OpinionatedMCP


class TestExampleMCPServer(unittest.TestCase):
    def setUp(self):
        self.google_client_id = "test_client_id"
        self.base_url = "http://localhost:8000"

    def test_init(self):
        """Test ExampleMCPServer initialization"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        assert_that(server.google_client_id, is_(self.google_client_id))
        assert_that(server.base_url, is_(self.base_url))
        assert_that(server, has_property("session_key"))
        assert_that(server, has_property("server"))
        assert_that(server.server, instance_of(OpinionatedMCP))

    def test_server_properties(self):
        """Test that the wrapped server has correct properties"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        assert_that(server.server.name, is_("Example MCP Server"))
        assert_that(server.server.google_client_id, is_(self.google_client_id))
        assert_that(server.server.base_url, is_(self.base_url))

    def test_tools_registration(self):
        """Test that tools are properly registered"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        # Check that tools were registered by checking MCP server tools
        async def check_tools():
            tools = await server.server.mcp.list_tools()
            tool_names = [tool.name for tool in tools]
            assert_that("echo" in tool_names, is_(True))
            assert_that("add" in tool_names, is_(True))

        asyncio.run(check_tools())

    def test_echo_tool(self):
        """Test echo tool functionality"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        async def check_echo_tool():
            # Find the echo tool
            tools = await server.server.mcp.list_tools()
            echo_tool = next(tool for tool in tools if tool.name == "echo")

            assert_that(echo_tool.name, is_("echo"))
            assert_that(echo_tool.description, is_("Echo back the input text"))

        asyncio.run(check_echo_tool())

    def test_add_tool(self):
        """Test add tool functionality"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        async def check_add_tool():
            # Find the add tool
            tools = await server.server.mcp.list_tools()
            add_tool = next(tool for tool in tools if tool.name == "add")

            assert_that(add_tool.name, is_("add"))
            assert_that(add_tool.description, is_("Add two numbers"))

        asyncio.run(check_add_tool())

    def test_echo_tool_execution(self):
        """Test that echo tool logic works correctly"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        # Test the echo tool function directly
        result = server._echo_tool("test message")
        assert_that(result, is_("Echo: test message"))

    def test_add_tool_execution(self):
        """Test that add tool logic works correctly"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        # Test the add tool function directly
        result = server._add_tool(5, 3)
        assert_that(result, is_(8))

    def test_endpoints_registration(self):
        """Test that authenticated endpoints are registered"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        # Check routes were added
        routes = [route for route in server.server.app.routes if hasattr(route, "path")]
        route_paths = [route.path for route in routes]

        assert_that("/profile" in route_paths, is_(True))
        assert_that("/data" in route_paths, is_(True))

    def test_profile_endpoint_not_authenticated(self):
        """Test profile endpoint returns 401 when not authenticated"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        with TestClient(server.server.app) as client:
            response = client.get("/profile")
            assert_that(response.status_code, is_(401))

    def test_data_endpoint_get_not_authenticated(self):
        """Test data endpoint GET returns 401 when not authenticated"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        with TestClient(server.server.app) as client:
            response = client.get("/data")
            assert_that(response.status_code, is_(401))

    def test_data_endpoint_post_not_authenticated(self):
        """Test data endpoint POST returns 401 when not authenticated"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        with TestClient(server.server.app) as client:
            response = client.post("/data")
            assert_that(response.status_code, is_(401))

    @patch("opinionated_mcp.auth.GoogleOAuthHandler.get_user_from_request")
    def test_profile_endpoint_authenticated(self, mock_get_user):
        """Test profile endpoint returns user data when authenticated"""
        mock_get_user.return_value = "test@example.com"

        server = ExampleMCPServer(self.google_client_id, self.base_url)

        with TestClient(server.server.app) as client:
            response = client.get("/profile")
            assert_that(response.status_code, is_(200))

            data = response.json()
            assert_that(data["user_id"], is_("test@example.com"))
            assert_that(data["profile"], is_("User profile data"))
            assert_that(data["authenticated"], is_(True))

    @patch("opinionated_mcp.auth.GoogleOAuthHandler.get_user_from_request")
    def test_data_endpoint_get_authenticated(self, mock_get_user):
        """Test data endpoint GET returns user data when authenticated"""
        mock_get_user.return_value = "test@example.com"

        server = ExampleMCPServer(self.google_client_id, self.base_url)

        with TestClient(server.server.app) as client:
            response = client.get("/data")
            assert_that(response.status_code, is_(200))

            data = response.json()
            assert_that(data["user_id"], is_("test@example.com"))
            assert_that(data["data"], is_("User-specific data"))

    @patch("opinionated_mcp.auth.GoogleOAuthHandler.get_user_from_request")
    def test_data_endpoint_post_authenticated(self, mock_get_user):
        """Test data endpoint POST returns success when authenticated"""
        mock_get_user.return_value = "test@example.com"

        server = ExampleMCPServer(self.google_client_id, self.base_url)

        with TestClient(server.server.app) as client:
            response = client.post("/data")
            assert_that(response.status_code, is_(200))

            data = response.json()
            assert_that(data["user_id"], is_("test@example.com"))
            assert_that(data["message"], is_("Data updated successfully"))


class TestCreateExampleServer(unittest.TestCase):
    def test_create_example_server(self):
        """Test factory function creates correct server"""
        google_client_id = "test_client"
        base_url = "http://test.example"

        server = create_example_server(google_client_id, base_url)

        assert_that(server, instance_of(ExampleMCPServer))
        assert_that(server.google_client_id, is_(google_client_id))
        assert_that(server.base_url, is_(base_url))

    def test_create_example_server_different_params(self):
        """Test factory function with different parameters"""
        google_client_id = "different_client"
        base_url = "https://different.example.com"

        server = create_example_server(google_client_id, base_url)

        assert_that(server, instance_of(ExampleMCPServer))
        assert_that(server.google_client_id, is_(google_client_id))
        assert_that(server.base_url, is_(base_url))
        assert_that(server.server.name, is_("Example MCP Server"))

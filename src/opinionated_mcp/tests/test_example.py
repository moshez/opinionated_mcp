"""Tests for example subpackage"""

import asyncio
import unittest
from hamcrest import assert_that, is_, instance_of, has_property
from opinionated_mcp.example import ExampleMCPServer, create_example_server, user_data
from opinionated_mcp.server import OpinionatedMCP


class TestExampleMCPServer(unittest.TestCase):
    def setUp(self):
        self.google_client_id = "test_client_id"
        self.base_url = "http://localhost:8000"
        # Clear user data before each test
        user_data.clear()

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
            assert_that("write_name" in tool_names, is_(True))
            assert_that("read_name" in tool_names, is_(True))

        asyncio.run(check_tools())

    def test_write_name_tool(self):
        """Test write_name tool functionality"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        async def check_write_name_tool():
            # Find the write_name tool
            tools = await server.server.mcp.list_tools()
            write_name_tool = next(tool for tool in tools if tool.name == "write_name")

            assert_that(write_name_tool.name, is_("write_name"))
            assert_that(write_name_tool.description, is_("Store your name"))

        asyncio.run(check_write_name_tool())

    def test_read_name_tool(self):
        """Test read_name tool functionality"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        async def check_read_name_tool():
            # Find the read_name tool
            tools = await server.server.mcp.list_tools()
            read_name_tool = next(tool for tool in tools if tool.name == "read_name")

            assert_that(read_name_tool.name, is_("read_name"))
            assert_that(read_name_tool.description, is_("Get your stored name"))

        asyncio.run(check_read_name_tool())

    def test_write_name_tool_execution(self):
        """Test that write_name tool logic works correctly"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        # Test the decorated tool function (user_id is injected automatically)
        result = server._write_name("John Doe")
        assert_that(
            result,
            is_("Stored name 'John Doe' for user authenticated_user@example.com"),
        )
        assert_that(user_data["authenticated_user@example.com"], is_("John Doe"))

    def test_read_name_tool_execution_with_data(self):
        """Test that read_name tool works when data exists"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        # Pre-populate user data
        user_data["authenticated_user@example.com"] = "John Doe"

        # Test the decorated tool function (user_id is injected automatically)
        result = server._read_name()
        assert_that(result, is_("Your stored name is: John Doe"))

    def test_read_name_tool_execution_no_name_stored(self):
        """Test that read_name tool returns appropriate message when no name is
        stored"""
        server = ExampleMCPServer(self.google_client_id, self.base_url)

        # Test with user who has no stored name (user_id is injected
        # automatically)
        result = server._read_name()
        assert_that(result, is_("Your stored name is: No name stored"))


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

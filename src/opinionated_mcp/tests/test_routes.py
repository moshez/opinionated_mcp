"""Tests for routes module"""

import unittest
import httpx
import respx
from unittest.mock import patch
from hamcrest import assert_that, is_, contains_string, has_key
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from opinionated_mcp.routes import setup_routes
from opinionated_mcp.auth import GoogleOAuthHandler
from opinionated_mcp.crypto import SessionCrypto, generate_session_key


class TestSetupRoutes(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

        self.crypto = SessionCrypto(generate_session_key())
        self.oauth_handler = GoogleOAuthHandler(
            client_id="test_client_id",
            redirect_uri="http://localhost:8000/callback",
            crypto=self.crypto,
        )

        setup_routes(
            self.app, self.oauth_handler, "Test Server", "http://localhost:8000"
        )

    def test_home_route(self):
        """Test home route returns server info"""
        with TestClient(self.app) as client:
            response = client.get("/")
            assert_that(response.status_code, is_(200))
            data = response.json()
            assert_that(data["message"], is_("Test Server MCP Server"))
            assert_that(data["login"], is_("/login"))
            assert_that(data["mcp_endpoint"], is_("/mcp"))

    def test_login_route(self):
        """Test login route redirects to Google OAuth"""
        with TestClient(self.app) as client:
            response = client.get("/login", follow_redirects=False)
            assert_that(response.status_code, is_(307))  # FastAPI redirect response
            # Should redirect to Google OAuth
            assert_that(
                response.headers["location"], contains_string("accounts.google.com")
            )

    def test_callback_route_with_error(self):
        """Test callback route with OAuth error parameter"""
        with TestClient(self.app) as client:
            response = client.get("/callback?error=access_denied")
            assert_that(response.status_code, is_(400))
            assert_that(response.json(), has_key("detail"))
            assert_that(
                response.json()["detail"], contains_string("OAuth error: access_denied")
            )

    def test_callback_route_missing_code(self):
        """Test callback route with missing code parameter"""
        with TestClient(self.app) as client:
            response = client.get("/callback?state=test_state")
            assert_that(response.status_code, is_(400))
            assert_that(response.json(), has_key("detail"))
            assert_that(
                response.json()["detail"], contains_string("Missing code or state")
            )

    def test_callback_route_missing_state(self):
        """Test callback route with missing state parameter"""
        with TestClient(self.app) as client:
            response = client.get("/callback?code=test_code")
            assert_that(response.status_code, is_(400))
            assert_that(response.json(), has_key("detail"))
            assert_that(
                response.json()["detail"], contains_string("Missing code or state")
            )

    @respx.mock
    def test_callback_route_success(self):
        """Test successful callback route with mocked OAuth endpoints"""
        # Mock the Google OAuth endpoints that the callback will hit
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "test_token"})
        )
        respx.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )

        with TestClient(self.app) as client:
            # First, get a session with the proper state/verifier by visiting login
            login_response = client.get("/login", follow_redirects=False)

            # Extract the actual state from the redirect URL
            redirect_url = login_response.headers["location"]
            import urllib.parse as urlparse

            parsed_url = urlparse.urlparse(redirect_url)
            query_params = urlparse.parse_qs(parsed_url.query)
            actual_state = query_params["state"][0]

            # Extract session cookie from login response
            session_cookie = None
            for cookie_header in login_response.headers.get_list("set-cookie"):
                if "session=" in cookie_header:
                    session_cookie = cookie_header.split(";")[0]
                    break

            # Now make callback request with the same session and correct state
            headers = {"cookie": session_cookie} if session_cookie else {}
            response = client.get(
                f"/callback?code=test_code&state={actual_state}", headers=headers
            )

            assert_that(response.status_code, is_(200))
            data = response.json()
            assert_that(data["message"], is_("Successfully authenticated!"))
            assert_that(data["user"], is_("test@example.com"))
            assert_that(data["mcp_endpoint"], is_("/mcp"))

    def test_current_user_route_not_authenticated(self):
        """Test user route when not authenticated"""
        with TestClient(self.app) as client:
            response = client.get("/user")
            assert_that(response.status_code, is_(401))
            assert_that(response.json(), has_key("detail"))
            assert_that(response.json()["detail"], contains_string("Not authenticated"))

    @respx.mock
    def test_current_user_route_authenticated(self):
        """Test user route when authenticated with valid session"""
        # Mock the Google OAuth endpoints
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "test_token"})
        )
        respx.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )

        with TestClient(self.app) as client:
            # First, authenticate by doing the full OAuth flow
            login_response = client.get("/login", follow_redirects=False)

            # Extract the actual state from the redirect URL
            redirect_url = login_response.headers["location"]
            import urllib.parse as urlparse

            parsed_url = urlparse.urlparse(redirect_url)
            query_params = urlparse.parse_qs(parsed_url.query)
            actual_state = query_params["state"][0]

            # Extract session cookie
            session_cookie = None
            for cookie_header in login_response.headers.get_list("set-cookie"):
                if "session=" in cookie_header:
                    session_cookie = cookie_header.split(";")[0]
                    break

            # Complete OAuth callback to authenticate
            headers = {"cookie": session_cookie} if session_cookie else {}
            callback_response = client.get(
                f"/callback?code=test_code&state={actual_state}", headers=headers
            )
            assert_that(callback_response.status_code, is_(200))

            # Update session cookie from callback response
            for cookie_header in callback_response.headers.get_list("set-cookie"):
                if "session=" in cookie_header:
                    session_cookie = cookie_header.split(";")[0]
                    break

            # Now test the authenticated user endpoint
            headers = {"cookie": session_cookie} if session_cookie else {}
            response = client.get("/user", headers=headers)
            assert_that(response.status_code, is_(200))
            data = response.json()
            assert_that(data["user_id"], is_("test@example.com"))
            assert_that(data["authenticated"], is_(True))

    def test_current_user_route_invalid_session(self):
        """Test user route when authenticated but session is invalid"""
        # We need to test the HTTP route path where session.authenticated=True
        # but oauth_handler.get_user_from_request returns None
        # This happens when session is corrupted or crypto fails

        # Create a corrupted session scenario by testing with a session that has
        # authenticated=True but invalid user_id that can't be decrypted

        # Mock the oauth handler to simulate authenticated=True but invalid user_id
        with patch.object(self.oauth_handler, "get_user_from_request") as mock_get_user:
            # First call returns None (simulating invalid session)
            mock_get_user.return_value = None

            # Mock session to return authenticated=True to pass first check
            with patch("fastapi.Request") as mock_request_class:
                mock_request = mock_request_class.return_value
                mock_request.session.get.return_value = True  # authenticated=True

                # Find the current_user route function and call it directly
                for route in self.app.routes:
                    if hasattr(route, "path") and route.path == "/user":
                        import asyncio

                        with self.assertRaises(HTTPException) as context:
                            asyncio.run(route.endpoint(mock_request))

                        assert_that(context.exception.status_code, is_(401))
                        assert_that(
                            str(context.exception.detail),
                            contains_string("Invalid session"),
                        )
                        break

    def test_logout_route(self):
        """Test logout route clears session"""
        with TestClient(self.app) as client:
            response = client.post("/logout")
            assert_that(response.status_code, is_(200))
            assert_that(response.json()["message"], is_("Logged out"))

    def test_oauth_metadata_route(self):
        """Test OAuth metadata endpoint returns proper discovery document"""
        with TestClient(self.app) as client:
            response = client.get("/.well-known/oauth-authorization-server")
            assert_that(response.status_code, is_(200))
            data = response.json()
            assert_that(data["issuer"], is_("http://localhost:8000"))
            assert_that(
                data["authorization_endpoint"], is_("http://localhost:8000/login")
            )
            assert_that(data, has_key("response_types_supported"))
            assert_that(data, has_key("grant_types_supported"))
            assert_that(data, has_key("code_challenge_methods_supported"))
            assert_that("code" in data["response_types_supported"], is_(True))
            assert_that(
                "authorization_code" in data["grant_types_supported"], is_(True)
            )
            assert_that("S256" in data["code_challenge_methods_supported"], is_(True))

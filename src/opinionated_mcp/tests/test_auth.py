"""Tests for auth module"""

import unittest
import httpx
import respx
from unittest.mock import Mock
from hamcrest import assert_that, is_, not_, contains_string, instance_of
from fastapi import HTTPException
from opinionated_mcp.auth import GoogleOAuthHandler
from opinionated_mcp.crypto import SessionCrypto, generate_session_key


class TestGoogleOAuthHandler(unittest.TestCase):
    def setUp(self):
        self.crypto = SessionCrypto(generate_session_key())
        self.oauth_handler = GoogleOAuthHandler(
            client_id="test_client_id",
            redirect_uri="http://localhost:8000/callback",
            crypto=self.crypto,
        )
        self.mock_request = Mock()
        self.mock_request.session = {}

    def test_init(self):
        handler = GoogleOAuthHandler(
            client_id="test_client",
            redirect_uri="http://test.com/callback",
            crypto=self.crypto,
        )
        assert_that(handler.client_id, is_("test_client"))
        assert_that(handler.redirect_uri, is_("http://test.com/callback"))
        assert_that(handler.crypto, is_(self.crypto))

    def test_generate_auth_url(self):
        auth_url = self.oauth_handler.generate_auth_url(self.mock_request)

        assert_that(
            auth_url, contains_string("https://accounts.google.com/o/oauth2/v2/auth")
        )
        assert_that(auth_url, contains_string("client_id=test_client_id"))
        assert_that(
            auth_url, contains_string("redirect_uri=http://localhost:8000/callback")
        )
        assert_that(auth_url, contains_string("scope=openid email profile"))
        assert_that(auth_url, contains_string("response_type=code"))
        assert_that(auth_url, contains_string("code_challenge_method=S256"))

        assert_that("oauth_state" in self.mock_request.session, is_(True))
        assert_that("code_verifier" in self.mock_request.session, is_(True))
        assert_that(auth_url, contains_string(self.mock_request.session["oauth_state"]))

    def test_handle_callback_invalid_state(self):
        self.mock_request.session = {"oauth_state": "correct_state"}

        async def test_invalid_state():
            await self.oauth_handler.handle_callback(
                self.mock_request, "test_code", "wrong_state"
            )

        with self.assertRaises(HTTPException) as context:
            import asyncio

            asyncio.run(test_invalid_state())

        assert_that(context.exception.status_code, is_(400))
        assert_that(str(context.exception.detail), contains_string("Invalid state"))

    def test_handle_callback_missing_verifier(self):
        self.mock_request.session = {"oauth_state": "test_state"}

        async def test_missing_verifier():
            await self.oauth_handler.handle_callback(
                self.mock_request, "test_code", "test_state"
            )

        with self.assertRaises(HTTPException) as context:
            import asyncio

            asyncio.run(test_missing_verifier())

        assert_that(context.exception.status_code, is_(400))
        assert_that(
            str(context.exception.detail), contains_string("Missing code verifier")
        )

    def test_get_user_from_request_authenticated(self):
        user_email = "test@example.com"
        encrypted_user_id = self.crypto.encrypt_user_id(user_email)

        self.mock_request.session = {
            "authenticated": True,
            "user_id": encrypted_user_id,
        }

        result = self.oauth_handler.get_user_from_request(self.mock_request)
        assert_that(result, is_(user_email))

    def test_get_user_from_request_not_authenticated(self):
        self.mock_request.session = {"authenticated": False}

        result = self.oauth_handler.get_user_from_request(self.mock_request)
        assert_that(result, is_(None))

    def test_get_user_from_request_no_user_id(self):
        self.mock_request.session = {"authenticated": True}

        result = self.oauth_handler.get_user_from_request(self.mock_request)
        assert_that(result, is_(None))

    def test_get_user_from_request_invalid_encryption(self):
        self.mock_request.session = {
            "authenticated": True,
            "user_id": "invalid_encrypted_data",
        }

        result = self.oauth_handler.get_user_from_request(self.mock_request)
        assert_that(result, is_(None))

    def test_generate_code_verifier(self):
        verifier = self.oauth_handler._generate_code_verifier()
        assert_that(verifier, instance_of(str))
        assert_that(len(verifier) > 0, is_(True))

    def test_generate_code_challenge(self):
        verifier = "test_verifier"
        challenge = self.oauth_handler._generate_code_challenge(verifier)
        assert_that(challenge, instance_of(str))
        assert_that(len(challenge) > 0, is_(True))
        assert_that(challenge, not_(is_(verifier)))

    @respx.mock
    def test_handle_callback_success(self):
        """Test successful OAuth callback using real HTTP mocking"""
        # Mock the Google OAuth token endpoint
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "test_token"})
        )

        # Mock the Google tokeninfo endpoint
        respx.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )

        self.mock_request.session = {
            "oauth_state": "test_state",
            "code_verifier": "test_verifier",
        }

        async def test_success():
            result = await self.oauth_handler.handle_callback(
                self.mock_request, "test_code", "test_state"
            )

            assert_that(result, is_("test@example.com"))
            assert_that(self.mock_request.session["authenticated"], is_(True))
            assert_that("user_id" in self.mock_request.session, is_(True))

        import asyncio

        asyncio.run(test_success())

    @respx.mock
    def test_exchange_code_for_user_success(self):
        """Test successful token exchange using real HTTP client"""
        # Mock the Google OAuth token endpoint
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "test_token"})
        )

        # Mock the Google tokeninfo endpoint
        respx.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(200, json={"email": "test@example.com"})
        )

        async def test_success():
            result = await self.oauth_handler._exchange_code_for_user(
                "test_code", "test_verifier"
            )
            assert_that(result, is_("test@example.com"))

        import asyncio

        asyncio.run(test_success())

    @respx.mock
    def test_exchange_code_for_user_token_failure(self):
        """Test token exchange failure using real HTTP client"""
        # Mock failed token request
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(400, json={"error": "invalid_grant"})
        )

        async def test_token_failure():
            await self.oauth_handler._exchange_code_for_user(
                "test_code", "test_verifier"
            )

        with self.assertRaises(HTTPException) as context:
            import asyncio

            asyncio.run(test_token_failure())

        assert_that(context.exception.status_code, is_(400))
        assert_that(
            str(context.exception.detail), contains_string("Token exchange failed")
        )

    @respx.mock
    def test_exchange_code_for_user_user_info_failure(self):
        """Test user info retrieval failure using real HTTP client"""
        # Mock successful token request
        respx.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "test_token"})
        )

        # Mock failed tokeninfo request
        respx.get("https://oauth2.googleapis.com/tokeninfo").mock(
            return_value=httpx.Response(400, json={"error": "invalid_token"})
        )

        async def test_user_failure():
            await self.oauth_handler._exchange_code_for_user(
                "test_code", "test_verifier"
            )

        with self.assertRaises(HTTPException) as context:
            import asyncio

            asyncio.run(test_user_failure())

        assert_that(context.exception.status_code, is_(400))
        assert_that(
            str(context.exception.detail), contains_string("Failed to get user info")
        )

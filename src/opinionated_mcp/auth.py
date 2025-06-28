"""OAuth authentication utilities for OpinionatedMCP"""

import secrets
import base64
import hashlib
import httpx
from typing import Optional
from fastapi import HTTPException, Request
from .crypto import SessionCrypto


class GoogleOAuthHandler:
    """Handles Google OAuth flow with PKCE"""

    def __init__(self, client_id: str, redirect_uri: str, crypto: SessionCrypto):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.crypto = crypto

    def generate_auth_url(self, request: Request) -> str:
        """Generate Google OAuth authorization URL with PKCE"""
        state = secrets.token_urlsafe(32)
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)

        request.session["oauth_state"] = state
        request.session["code_verifier"] = code_verifier

        return (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&scope=openid email profile"
            f"&response_type=code"
            f"&state={state}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
        )

    async def handle_callback(self, request: Request, code: str, state: str) -> str:
        """Handle OAuth callback and return user email"""
        if request.session.get("oauth_state") != state:
            raise HTTPException(status_code=400, detail="Invalid state")

        code_verifier = request.session.get("code_verifier")
        if not code_verifier:
            raise HTTPException(status_code=400, detail="Missing code verifier")

        user_email = await self._exchange_code_for_user(code, code_verifier)

        encrypted_user_id = self.crypto.encrypt_user_id(user_email)
        request.session["user_id"] = encrypted_user_id
        request.session["authenticated"] = True

        return user_email

    def get_user_from_request(self, request: Request) -> Optional[str]:
        """Extract and decrypt user ID from request session"""
        if not request.session.get("authenticated"):
            return None

        encrypted_user_id = request.session.get("user_id")
        if not encrypted_user_id:
            return None

        try:
            return self.crypto.decrypt_user_id(encrypted_user_id)
        except Exception:
            return None

    async def _exchange_code_for_user(self, code: str, code_verifier: str) -> str:
        """Exchange OAuth code for user email"""
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "code": code,
                    "code_verifier": code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if token_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Token exchange failed")

            access_token = token_response.json()["access_token"]

            user_response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}"
            )

            if user_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")

            return user_response.json()["email"]

    def _generate_code_verifier(self) -> str:
        """Generate PKCE code verifier"""
        return (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .decode("utf-8")
            .rstrip("=")
        )

    def _generate_code_challenge(self, verifier: str) -> str:
        """Generate PKCE code challenge from verifier"""
        digest = hashlib.sha256(verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

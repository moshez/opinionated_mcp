"""Cryptographic utilities for OpinionatedMCP"""

from cryptography.fernet import Fernet


def generate_session_key() -> str:
    """Generate a session key for Fernet encryption"""
    return Fernet.generate_key().decode()


class SessionCrypto:
    """Handles encryption and decryption of session data"""

    def __init__(self, session_key: str):
        self.session_key = session_key
        self.fernet = Fernet(session_key.encode())

    def encrypt_user_id(self, user_id: str) -> str:
        """Encrypt a user ID for session storage"""
        return self.fernet.encrypt(user_id.encode()).decode()

    def decrypt_user_id(self, encrypted_user_id: str) -> str:
        """Decrypt a user ID from session storage"""
        return self.fernet.decrypt(encrypted_user_id.encode()).decode()

    def update_key(self, new_session_key: str):
        """Update the session key"""
        self.session_key = new_session_key
        self.fernet = Fernet(new_session_key.encode())

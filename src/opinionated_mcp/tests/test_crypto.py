"""Tests for crypto module"""

import unittest
from hamcrest import assert_that, is_, not_, instance_of, raises, calling
from cryptography.fernet import Fernet
from opinionated_mcp.crypto import generate_session_key, SessionCrypto


class TestGenerateSessionKey(unittest.TestCase):
    def test_generate_session_key_returns_string(self):
        key = generate_session_key()
        assert_that(key, instance_of(str))

    def test_generate_session_key_is_valid_fernet_key(self):
        key = generate_session_key()
        fernet = Fernet(key.encode())
        assert_that(fernet, instance_of(Fernet))

    def test_generate_session_key_returns_different_keys(self):
        key1 = generate_session_key()
        key2 = generate_session_key()
        assert_that(key1, not_(is_(key2)))


class TestSessionCrypto(unittest.TestCase):
    def test_init_with_valid_key(self):
        key = generate_session_key()
        crypto = SessionCrypto(key)
        assert_that(crypto.session_key, is_(key))
        assert_that(crypto.fernet, instance_of(Fernet))

    def test_encrypt_decrypt_user_id(self):
        key = generate_session_key()
        crypto = SessionCrypto(key)
        user_id = "test@example.com"

        encrypted = crypto.encrypt_user_id(user_id)
        assert_that(encrypted, instance_of(str))
        assert_that(encrypted, not_(is_(user_id)))

        decrypted = crypto.decrypt_user_id(encrypted)
        assert_that(decrypted, is_(user_id))

    def test_encrypt_different_user_ids_different_output(self):
        key = generate_session_key()
        crypto = SessionCrypto(key)

        encrypted1 = crypto.encrypt_user_id("user1@example.com")
        encrypted2 = crypto.encrypt_user_id("user2@example.com")

        assert_that(encrypted1, not_(is_(encrypted2)))

    def test_decrypt_invalid_data_raises_exception(self):
        key = generate_session_key()
        crypto = SessionCrypto(key)

        assert_that(
            calling(crypto.decrypt_user_id).with_args("invalid_encrypted_data"),
            raises(Exception),
        )

    def test_update_key(self):
        old_key = generate_session_key()
        new_key = generate_session_key()
        crypto = SessionCrypto(old_key)

        user_id = "test@example.com"
        old_encrypted = crypto.encrypt_user_id(user_id)

        crypto.update_key(new_key)
        assert_that(crypto.session_key, is_(new_key))

        new_encrypted = crypto.encrypt_user_id(user_id)
        assert_that(new_encrypted, not_(is_(old_encrypted)))

        assert_that(crypto.decrypt_user_id(new_encrypted), is_(user_id))

    def test_decrypt_with_old_key_after_update_fails(self):
        old_key = generate_session_key()
        new_key = generate_session_key()
        crypto = SessionCrypto(old_key)

        user_id = "test@example.com"
        old_encrypted = crypto.encrypt_user_id(user_id)

        crypto.update_key(new_key)

        assert_that(
            calling(crypto.decrypt_user_id).with_args(old_encrypted), raises(Exception)
        )

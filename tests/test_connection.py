"""Tests for asher.connection module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from asher.connection import (
    _keyring_available,
    _keyring_delete,
    _keyring_load,
    _keyring_save,
)


class TestKeyringAvailable:
    def test_returns_true_when_keyring_works(self):
        with patch("asher.connection.keyring.get_keyring") as mock_get:
            mock_get.return_value = MagicMock()
            assert _keyring_available() is True

    def test_returns_false_when_keyring_raises(self):
        with patch("asher.connection.keyring.get_keyring") as mock_get:
            mock_get.side_effect = Exception("No keyring available")
            assert _keyring_available() is False


class TestKeyringLoad:
    def test_loads_credentials_successfully(self):
        with patch("asher.connection.keyring.get_password") as mock_get:
            mock_get.side_effect = ["test@example.com", "secret123"]
            email, password = _keyring_load()
            assert email == "test@example.com"
            assert password == "secret123"

    def test_returns_empty_strings_when_no_credentials(self):
        with patch("asher.connection.keyring.get_password") as mock_get:
            mock_get.return_value = None
            email, password = _keyring_load()
            assert email == ""
            assert password == ""

    def test_returns_empty_on_exception(self):
        with patch("asher.connection.keyring.get_password") as mock_get:
            mock_get.side_effect = Exception("Keyring error")
            email, password = _keyring_load()
            assert email == ""
            assert password == ""

    def test_uses_correct_service_and_keys(self):
        with patch("asher.connection.keyring.get_password") as mock_get:
            mock_get.return_value = None
            _keyring_load()
            calls = mock_get.call_args_list
            assert calls[0][0] == ("asher-cli", "email")
            assert calls[1][0] == ("asher-cli", "password")


class TestKeyringSave:
    def test_saves_credentials_successfully(self):
        with patch("asher.connection.keyring.set_password") as mock_set:
            result = _keyring_save("test@example.com", "secret123")
            assert result is True
            assert mock_set.call_count == 2

    def test_returns_false_on_exception(self):
        with patch("asher.connection.keyring.set_password") as mock_set:
            mock_set.side_effect = Exception("Keyring error")
            result = _keyring_save("test@example.com", "secret123")
            assert result is False

    def test_uses_correct_service_and_keys(self):
        with patch("asher.connection.keyring.set_password") as mock_set:
            _keyring_save("test@example.com", "secret123")
            calls = mock_set.call_args_list
            assert calls[0][0] == ("asher-cli", "email", "test@example.com")
            assert calls[1][0] == ("asher-cli", "password", "secret123")


class TestKeyringDelete:
    def test_deletes_all_credentials(self):
        with patch("asher.connection.keyring.delete_password") as mock_delete:
            _keyring_delete()
            assert mock_delete.call_count == 3

    def test_uses_correct_service_and_keys(self):
        with patch("asher.connection.keyring.delete_password") as mock_delete:
            _keyring_delete()
            calls = mock_delete.call_args_list
            assert calls[0][0] == ("asher-cli", "email")
            assert calls[1][0] == ("asher-cli", "password")
            assert calls[2][0] == ("asher-cli", "preferred_robot")

    def test_suppresses_exceptions(self):
        with patch("asher.connection.keyring.delete_password") as mock_delete:
            mock_delete.side_effect = Exception("Keyring error")
            _keyring_delete()

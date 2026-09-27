"""Tests for asher.tui.connection module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from asher.core import credentials


class TestEnvCredentials:
    """The environment is a development convenience, never an install's source."""

    def test_ignored_outside_dev_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LITTER_ROBOT_USER", "env@example.com")
        monkeypatch.setenv("LITTER_ROBOT_PASSWORD", "envpw")
        monkeypatch.delenv("ASHER_CLI_DEV_MODE", raising=False)
        assert credentials.from_env() == ("", "")

    def test_read_in_dev_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LITTER_ROBOT_USER", "env@example.com")
        monkeypatch.setenv("LITTER_ROBOT_PASSWORD", "envpw")
        monkeypatch.setenv("ASHER_CLI_DEV_MODE", "true")
        assert credentials.from_env() == ("env@example.com", "envpw")

    def test_dev_mode_flag_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LITTER_ROBOT_USER", "env@example.com")
        monkeypatch.setenv("LITTER_ROBOT_PASSWORD", "envpw")
        monkeypatch.setenv("ASHER_CLI_DEV_MODE", "TRUE")
        assert credentials.from_env() == ("env@example.com", "envpw")

    def test_dev_mode_with_nothing_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LITTER_ROBOT_USER", raising=False)
        monkeypatch.delenv("LITTER_ROBOT_PASSWORD", raising=False)
        monkeypatch.setenv("ASHER_CLI_DEV_MODE", "true")
        assert credentials.from_env() == ("", "")


class TestCredentialsAvailable:
    """Gate for `asher watch start`, which must not report a pid for a doomed process."""

    def test_a_cached_token_is_enough(self) -> None:
        with patch("asher.core.credentials.load_token", return_value="tok"):
            assert credentials.available() is True

    def test_keyring_email_and_password(self) -> None:
        with (
            patch("asher.core.credentials.load_token", return_value=None),
            patch("asher.core.credentials.keyring_available", return_value=True),
            patch("asher.core.credentials.load", return_value=("a@b.com", "pw")),
        ):
            assert credentials.available() is True

    def test_false_when_nothing_is_stored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ASHER_CLI_DEV_MODE", raising=False)
        with (
            patch("asher.core.credentials.load_token", return_value=None),
            patch("asher.core.credentials.keyring_available", return_value=True),
            patch("asher.core.credentials.load", return_value=("", "")),
        ):
            assert credentials.available() is False

    def test_half_a_credential_is_not_enough(self) -> None:
        with (
            patch("asher.core.credentials.load_token", return_value=None),
            patch("asher.core.credentials.keyring_available", return_value=True),
            patch("asher.core.credentials.load", return_value=("a@b.com", "")),
        ):
            assert credentials.available() is False

    def test_falls_back_to_the_environment_in_dev_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ASHER_CLI_DEV_MODE", "true")
        monkeypatch.setenv("LITTER_ROBOT_USER", "env@example.com")
        monkeypatch.setenv("LITTER_ROBOT_PASSWORD", "envpw")
        with (
            patch("asher.core.credentials.load_token", return_value=None),
            patch("asher.core.credentials.keyring_available", return_value=False),
        ):
            assert credentials.available() is True


class TestKeyringAvailable:
    def test_returns_true_when_keyring_works(self):
        with patch("asher.core.credentials.keyring.get_keyring") as mock_get:
            mock_get.return_value = MagicMock()
            assert credentials.keyring_available() is True

    def test_returns_false_when_keyring_raises(self):
        with patch("asher.core.credentials.keyring.get_keyring") as mock_get:
            mock_get.side_effect = Exception("No keyring available")
            assert credentials.keyring_available() is False


class TestKeyringLoad:
    def test_loads_credentials_successfully(self):
        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.side_effect = ["test@example.com", "secret123"]
            email, password = credentials.load()
            assert email == "test@example.com"
            assert password == "secret123"

    def test_returns_empty_strings_when_no_credentials(self):
        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.return_value = None
            email, password = credentials.load()
            assert email == ""
            assert password == ""

    def test_returns_empty_on_exception(self):
        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.side_effect = Exception("Keyring error")
            email, password = credentials.load()
            assert email == ""
            assert password == ""

    def test_uses_correct_service_and_keys(self):
        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.return_value = None
            credentials.load()
            calls = mock_get.call_args_list
            assert calls[0][0] == ("asher-cli", "email")
            assert calls[1][0] == ("asher-cli", "password")


class TestKeyringSave:
    def test_saves_credentials_successfully(self):
        with patch("asher.core.credentials.keyring.set_password") as mock_set:
            result = credentials.save("test@example.com", "secret123")
            assert result is True
            assert mock_set.call_count == 2

    def test_returns_false_on_exception(self):
        with patch("asher.core.credentials.keyring.set_password") as mock_set:
            mock_set.side_effect = Exception("Keyring error")
            result = credentials.save("test@example.com", "secret123")
            assert result is False

    def test_uses_correct_service_and_keys(self):
        with patch("asher.core.credentials.keyring.set_password") as mock_set:
            credentials.save("test@example.com", "secret123")
            calls = mock_set.call_args_list
            assert calls[0][0] == ("asher-cli", "email", "test@example.com")
            assert calls[1][0] == ("asher-cli", "password", "secret123")


class TestKeyringDelete:
    def test_deletes_all_credentials(self):
        with patch("asher.core.credentials.keyring.delete_password") as mock_delete:
            credentials.delete()
            assert mock_delete.call_count == 4

    def test_uses_correct_service_and_keys(self):
        with patch("asher.core.credentials.keyring.delete_password") as mock_delete:
            credentials.delete()
            calls = mock_delete.call_args_list
            assert calls[0][0] == ("asher-cli", "email")
            assert calls[1][0] == ("asher-cli", "password")
            assert calls[2][0] == ("asher-cli", "preferred_robot")
            assert calls[3][0] == ("asher-cli", "token")

    def test_suppresses_exceptions(self):
        with patch("asher.core.credentials.keyring.delete_password") as mock_delete:
            mock_delete.side_effect = Exception("Keyring error")
            credentials.delete()


class TestKeyringTokenLoad:
    def test_loads_token_successfully(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.return_value = '{"access_token": "a", "id_token": "i", "refresh_token": "r"}'
            token = credentials.load_token()
            assert token == {"access_token": "a", "id_token": "i", "refresh_token": "r"}
            mock_get.assert_called_once_with("asher-cli", "token")

    def test_returns_none_when_no_token(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.return_value = None
            assert credentials.load_token() is None

    def test_returns_none_for_empty_string(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.return_value = ""
            assert credentials.load_token() is None

    def test_returns_none_on_invalid_json(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.return_value = "not json{"
            assert credentials.load_token() is None

    def test_returns_none_for_non_dict_json(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.return_value = '["not", "a", "dict"]'
            assert credentials.load_token() is None

    def test_returns_none_on_exception(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.get_password") as mock_get:
            mock_get.side_effect = Exception("Keyring error")
            assert credentials.load_token() is None


class TestKeyringTokenSave:
    def test_saves_token_as_json(self):
        import json

        from asher.core import credentials

        token = {"access_token": "a", "id_token": "i", "refresh_token": "r"}
        with patch("asher.core.credentials.keyring.set_password") as mock_set:
            credentials.save_token(token)
            mock_set.assert_called_once()
            assert mock_set.call_args[0][0] == "asher-cli"
            assert mock_set.call_args[0][1] == "token"
            assert json.loads(mock_set.call_args[0][2]) == token

    def test_none_token_deletes(self):
        from asher.core import credentials

        with (
            patch("asher.core.credentials.keyring.set_password") as mock_set,
            patch("asher.core.credentials.keyring.delete_password") as mock_del,
        ):
            credentials.save_token(None)
            mock_set.assert_not_called()
            mock_del.assert_called_once_with("asher-cli", "token")

    def test_empty_dict_deletes(self):
        from asher.core import credentials

        with (
            patch("asher.core.credentials.keyring.set_password") as mock_set,
            patch("asher.core.credentials.keyring.delete_password") as mock_del,
        ):
            credentials.save_token({})
            mock_set.assert_not_called()
            mock_del.assert_called_once_with("asher-cli", "token")

    def test_save_suppresses_exceptions(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.set_password") as mock_set:
            mock_set.side_effect = Exception("Keyring error")
            credentials.save_token({"access_token": "a"})  # should not raise

    def test_delete_on_none_suppresses_exceptions(self):
        from asher.core import credentials

        with patch("asher.core.credentials.keyring.delete_password") as mock_del:
            mock_del.side_effect = Exception("Keyring error")
            credentials.save_token(None)  # should not raise

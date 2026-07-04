"""Tests for asher.mcp_bridge module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from asher.mcp_bridge import main


class TestMain:
    def test_exits_nonzero_when_no_credentials(self):
        with (
            patch("keyring.get_password", return_value=None),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 1

    def test_launches_pylitterbot_mcp_with_env_credentials(self):
        mock_result = MagicMock(returncode=0)
        with (
            patch("keyring.get_password", side_effect=["test@example.com", "secret123"]),
            patch("asher.mcp_bridge.subprocess.run", return_value=mock_result) as mock_run,
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 0
        args, kwargs = mock_run.call_args
        assert args[0][1:] == ["-m", "pylitterbot.mcp"]
        assert kwargs["env"]["LITTER_ROBOT_USERNAME"] == "test@example.com"
        assert kwargs["env"]["LITTER_ROBOT_PASSWORD"] == "secret123"

    def test_propagates_child_exit_code(self):
        mock_result = MagicMock(returncode=3)
        with (
            patch("keyring.get_password", side_effect=["a@b.com", "pw"]),
            patch("asher.mcp_bridge.subprocess.run", return_value=mock_result),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 3

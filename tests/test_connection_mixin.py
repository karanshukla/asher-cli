"""Tests for asher.connection.ConnectionMixin."""

from __future__ import annotations

from asher.connection import ConnectionMixin


class TestConnectionMixinStructure:
    def test_class_exists(self):
        assert ConnectionMixin is not None

    def test_has_connect_worker_method(self):
        assert hasattr(ConnectionMixin, "_connect_worker")


class TestConnectWorker:
    def test_connect_worker_exists(self):
        assert hasattr(ConnectionMixin, "_connect_worker")
        assert callable(ConnectionMixin._connect_worker)

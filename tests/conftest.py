"""Shared pytest fixtures that keep ordinary unit tests offline."""

from __future__ import annotations

import socket

import pytest


class LiveNetworkBlocked(RuntimeError):
    """Raised when an unmarked test tries to open a TCP connection."""


def _guard_tcp(self: socket.socket, address: object) -> None:
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise LiveNetworkBlocked(
            f"Live network access is blocked in unit tests: {address!r}"
        )
    _REAL_CONNECT(self, address)


def _guard_tcp_ex(self: socket.socket, address: object) -> int:
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise LiveNetworkBlocked(
            f"Live network access is blocked in unit tests: {address!r}"
        )
    return _REAL_CONNECT_EX(self, address)


_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex


@pytest.fixture(autouse=True)
def block_live_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Block TCP for ordinary tests; a ``live`` mark explicitly opts out."""
    if request.node.get_closest_marker("live"):
        return
    monkeypatch.setattr(socket.socket, "connect", _guard_tcp)
    monkeypatch.setattr(socket.socket, "connect_ex", _guard_tcp_ex)


@pytest.fixture(autouse=True)
def no_real_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's real Comtrade key out of each test."""
    monkeypatch.delenv("COMTRADE_API_KEY", raising=False)

"""Regression tests for the shared offline network guard."""

import os
import socket

import pytest

BLOCKED = "Live network access is blocked"


def test_tcp_connect_is_blocked():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match=BLOCKED):
            sock.connect(("203.0.113.1", 80))
    finally:
        sock.close()


def test_tcp_connect_ex_is_blocked():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(RuntimeError, match=BLOCKED):
            sock.connect_ex(("203.0.113.1", 80))
    finally:
        sock.close()


def test_urllib_cannot_reach_a_live_api():
    from urllib.error import URLError
    from urllib.request import urlopen

    with pytest.raises((RuntimeError, URLError)) as excinfo:
        urlopen("http://203.0.113.1/", timeout=1)

    assert BLOCKED in str(excinfo.value)


def test_comtrade_key_is_not_visible_to_tests():
    assert os.getenv("COMTRADE_API_KEY") is None

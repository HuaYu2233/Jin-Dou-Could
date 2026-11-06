import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

from unittest.mock import MagicMock

from app.core.client_ip import get_client_ip, get_client_ip_from_scope, get_trusted_proxies


class TestTrustedProxies:
    def test_parsed_from_settings(self):
        assert "127.0.0.1" in get_trusted_proxies()
        assert "testclient" in get_trusted_proxies()

    def test_cached_singleton(self):
        assert get_trusted_proxies() is get_trusted_proxies()


class TestGetClientIpFromRequest:
    def test_trusted_proxy_honors_xff(self):
        req = MagicMock()
        req.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        req.client = MagicMock(host="127.0.0.1")
        assert get_client_ip(req) == "1.2.3.4"

    def test_trusted_proxy_honors_x_real_ip(self):
        req = MagicMock()
        req.headers = {"x-real-ip": "10.0.0.1"}
        req.client = MagicMock(host="127.0.0.1")
        assert get_client_ip(req) == "10.0.0.1"

    def test_untrusted_peer_ignores_spoofed_headers(self):
        req = MagicMock()
        req.headers = {"x-forwarded-for": "1.2.3.4"}
        req.client = MagicMock(host="8.8.8.8")
        assert get_client_ip(req) == "8.8.8.8"

    def test_no_client_returns_unknown(self):
        req = MagicMock()
        req.headers = {}
        req.client = None
        assert get_client_ip(req) == "unknown"


class TestGetClientIpFromScope:
    def test_trusted_proxy_honors_bytes_header(self):
        scope = {
            "client": ("127.0.0.1", 1234),
            "headers": [(b"x-forwarded-for", b"1.2.3.4, 5.6.7.8")],
        }
        assert get_client_ip_from_scope(scope) == "1.2.3.4"

    def test_untrusted_peer_ignores_bytes_header(self):
        scope = {
            "client": ("8.8.8.8", 1234),
            "headers": [(b"x-forwarded-for", b"1.2.3.4")],
        }
        assert get_client_ip_from_scope(scope) == "8.8.8.8"

    def test_x_real_ip_fallback(self):
        scope = {"client": ("127.0.0.1", 1234), "headers": [(b"x-real-ip", b"10.0.0.1")]}
        assert get_client_ip_from_scope(scope) == "10.0.0.1"

    def test_missing_client_returns_unknown(self):
        scope = {"headers": []}
        assert get_client_ip_from_scope(scope) == "unknown"

    def test_trusted_proxy_without_headers_returns_direct(self):
        scope = {"client": ("127.0.0.1", 1234), "headers": []}
        assert get_client_ip_from_scope(scope) == "127.0.0.1"

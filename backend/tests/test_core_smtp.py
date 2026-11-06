import os
import sys
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._env import setup_env

setup_env()

from typing import ClassVar
from unittest.mock import patch

import pytest

from app.core.smtp import send_smtp_message


class _FakeSMTP:
    instances: ClassVar[list["_FakeSMTP"]] = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args = None
        self.sent = None
        self.quit_called = False
        _FakeSMTP.instances.append(self)

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def sendmail(self, from_email, recipients, message):
        self.sent = (from_email, recipients, message)

    def quit(self):
        self.quit_called = True


def _make_message() -> MIMEText:
    return MIMEText("hello", "plain", "utf-8")


@pytest.fixture(autouse=True)
def _clear_instances():
    _FakeSMTP.instances.clear()
    yield
    _FakeSMTP.instances.clear()


class TestSendSmtpMessage:
    def test_sends_with_tls_and_login(self):
        msg = _make_message()
        with patch("app.core.smtp.smtplib.SMTP", _FakeSMTP):
            send_smtp_message(
                msg,
                ["to@example.com"],
                host="smtp.example.com",
                port=587,
                user="u",
                password="p",
                from_email="from@example.com",
                use_tls=True,
                timeout=15,
            )

        server = _FakeSMTP.instances[0]
        assert (server.host, server.port, server.timeout) == ("smtp.example.com", 587, 15)
        assert server.started_tls is True
        assert server.login_args == ("u", "p")
        assert server.sent == ("from@example.com", ["to@example.com"], msg.as_string())
        assert server.quit_called is True

    def test_skips_tls_and_login_when_disabled(self):
        with patch("app.core.smtp.smtplib.SMTP", _FakeSMTP):
            send_smtp_message(
                _make_message(),
                ["to@example.com"],
                host="smtp.example.com",
                port=25,
                user="",
                password="",
                from_email="from@example.com",
                use_tls=False,
            )

        server = _FakeSMTP.instances[0]
        assert server.started_tls is False
        assert server.login_args is None
        assert server.quit_called is True

    def test_quit_called_even_when_send_fails(self):
        class _FailingSMTP(_FakeSMTP):
            def sendmail(self, from_email, recipients, message):
                raise RuntimeError("smtp down")

        with patch("app.core.smtp.smtplib.SMTP", _FailingSMTP), pytest.raises(RuntimeError):
            send_smtp_message(
                _make_message(),
                ["to@example.com"],
                host="smtp.example.com",
                port=25,
                user="",
                password="",
                from_email="from@example.com",
                use_tls=False,
            )

        assert _FailingSMTP.instances[0].quit_called is True

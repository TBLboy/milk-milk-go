import importlib.util
from pathlib import Path

import pytest

from app.core.config import Settings


def load_smtp_test_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "packaging"
        / "windows"
        / "smtp_test.py"
    )
    spec = importlib.util.spec_from_file_location("milk_smtp_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeSMTP:
    def __init__(self, settings):
        self.settings = settings
        self.messages = []
        self.started_tls = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def ehlo(self):
        return None

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        assert username == self.settings.smtp_username
        assert password == self.settings.smtp_password

    def send_message(self, message):
        self.messages.append(message)


def smtp_settings(tmp_path, *, use_ssl=True):
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        smtp_username="sender@qq.com",
        smtp_password="smtp-authorization-code",
        bug_report_recipient="maintainer@example.com",
        smtp_use_ssl=use_ssl,
    )


def test_smtp_self_test_submits_message(tmp_path):
    module = load_smtp_test_module()
    settings = smtp_settings(tmp_path)
    client = FakeSMTP(settings)

    module.run_smtp_test(settings, smtp_factory=lambda _settings: client)

    assert len(client.messages) == 1
    message = client.messages[0]
    assert message["To"] == "maintainer@example.com"
    assert "SMTP 配置" in message.get_body(preferencelist=("plain",)).get_content()


def test_smtp_self_test_rejects_missing_credentials(tmp_path):
    module = load_smtp_test_module()
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        smtp_username=None,
        smtp_password=None,
    )

    with pytest.raises(module.SmtpSelfTestError) as error:
        module.run_smtp_test(settings)

    assert error.value.category == "CONFIG_MISSING"


def test_smtp_self_test_log_redacts_credentials(tmp_path):
    module = load_smtp_test_module()
    log_path = tmp_path / "smtp-install-test.log"

    module.write_smtp_test_log(
        log_path,
        status="failed",
        category="SMTPAuthenticationError",
        detail="login failed for smtp-authorization-code",
        secrets=["smtp-authorization-code"],
    )

    content = log_path.read_text(encoding="utf-8")
    assert "smtp-authorization-code" not in content
    assert "[REDACTED]" in content

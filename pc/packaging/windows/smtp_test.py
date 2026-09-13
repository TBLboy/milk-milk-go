from __future__ import annotations

import os
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, format_datetime
from pathlib import Path
from typing import Callable


SMTP_TEST_TIMEOUT_SECONDS = 8


class SmtpSelfTestError(RuntimeError):
    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category


def redact(value: object, secrets: list[str | None]) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:500]


def write_smtp_test_log(
    log_path: Path,
    *,
    status: str,
    category: str,
    detail: str,
    secrets: list[str | None],
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    safe_detail = redact(detail, secrets)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(
            f"{timestamp}\tstatus={status}\tcategory={category}\t"
            f"detail={safe_detail}\n"
        )


def build_test_message(settings) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "[辅料称重防错系统] 安装邮件反馈自检"
    message["From"] = formataddr(("牧衡辅料称重防错系统", settings.smtp_username))
    message["To"] = settings.bug_report_recipient
    message["Date"] = format_datetime(datetime.now().astimezone())
    message.set_content(
        "\n".join(
            [
                "这是一封由 Windows 安装程序发送的邮件反馈自检邮件。",
                "收到此邮件说明当前客户机 SMTP 配置可以从本机提交邮件。",
                "",
                f"自检时间：{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            ]
        )
    )
    return message


def _open_smtp(settings):
    if settings.smtp_use_ssl:
        return smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=SMTP_TEST_TIMEOUT_SECONDS,
        )
    return smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=SMTP_TEST_TIMEOUT_SECONDS,
    )


def run_smtp_test(
    settings,
    *,
    smtp_factory: Callable[[object], object] | None = None,
) -> None:
    if not settings.smtp_username or not settings.smtp_password:
        raise SmtpSelfTestError("CONFIG_MISSING", "SMTP 发件账号或授权码未配置")
    if not settings.bug_report_recipient:
        raise SmtpSelfTestError("RECIPIENT_MISSING", "BUG 反馈收件邮箱未配置")

    factory = smtp_factory or _open_smtp
    try:
        with factory(settings) as smtp:
            if not settings.smtp_use_ssl:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(build_test_message(settings))
    except Exception as exc:
        raise SmtpSelfTestError(type(exc).__name__, str(exc)) from exc


def _paths() -> tuple[Path, Path, Path, Path]:
    install_root = Path(__file__).resolve().parents[1]
    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    return (
        install_root,
        program_data / "MilkWeigh" / "config",
        program_data / "MilkWeigh" / "data",
        program_data / "MilkWeigh" / "logs",
    )


def main() -> int:
    install_root, config_dir, data_dir, log_dir = _paths()
    config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "smtp-install-test.log"
    secrets: list[str | None] = []
    settings = None

    try:
        os.chdir(config_dir)
        os.environ["MILK_DATA_DIR"] = str(data_dir)
        sys.path.insert(0, str(install_root / "server"))

        from app.core.config import get_settings

        settings = get_settings()
        secrets = [
            settings.smtp_password,
            settings.admin_recovery_secret_hash,
            settings.token_secret,
        ]
        run_smtp_test(settings)
    except SmtpSelfTestError as exc:
        write_smtp_test_log(
            log_path,
            status="failed",
            category=exc.category,
            detail=str(exc),
            secrets=secrets,
        )
        print(f"邮件反馈自检失败（{exc.category}），详情见日志。")
        return 1
    except Exception as exc:
        write_smtp_test_log(
            log_path,
            status="failed",
            category=type(exc).__name__,
            detail=str(exc),
            secrets=secrets,
        )
        print(f"邮件反馈自检失败（{type(exc).__name__}），详情见日志。")
        return 1

    write_smtp_test_log(
        log_path,
        status="success",
        category="SMTP_TEST_SUBMITTED",
        detail="测试邮件已提交到 SMTP 服务器",
        secrets=secrets,
    )
    print("邮件反馈自检成功：测试邮件已提交。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

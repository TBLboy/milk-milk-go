import json
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, format_datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.auth import current_user, require_admin
from app.core.config import get_settings
from app.db.models import BugReport, EvidenceFile, User
from app.db.session import get_db
from app.services.audit import write_audit


router = APIRouter(prefix="/bug-reports", tags=["bug-reports"])
MAX_BUG_IMAGES = 8


class BugReportCreate(BaseModel):
    source: Literal["pc", "app"]
    description: str = Field(min_length=1, max_length=5000)
    image_file_ids: list[str] = Field(default_factory=list, max_length=MAX_BUG_IMAGES)


class BugReportEmailConfigurationError(RuntimeError):
    pass


def _safe_error(value: object) -> str:
    settings = get_settings()
    text = str(value).replace("\r", " ").replace("\n", " ")
    for secret in (
        settings.smtp_password,
        settings.admin_recovery_secret_hash,
        settings.token_secret,
    ):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:1000]


def _send_message(message: EmailMessage) -> None:
    settings = get_settings()
    _require_email_config(settings)

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)


def _require_email_config(settings) -> None:
    if not settings.smtp_username or not settings.smtp_password:
        raise BugReportEmailConfigurationError("邮件发送服务尚未配置")


def send_bug_report_email(
    *,
    reporter: User,
    source: str,
    description: str,
    files: list[EvidenceFile],
) -> None:
    settings = get_settings()
    _require_email_config(settings)

    source_label = "电脑端" if source == "pc" else "平板端"
    message = EmailMessage()
    message["Subject"] = f"[辅料称重防错系统] {source_label} BUG 提交"
    message["From"] = formataddr(("牧衡辅料称重防错系统", settings.smtp_username))
    message["To"] = settings.bug_report_recipient
    message["Date"] = format_datetime(datetime.now().astimezone())
    message.set_content(
        "\n".join(
            [
                "收到一条新的 BUG 反馈：",
                "",
                f"提交来源：{source_label}",
                f"提交账号：{reporter.username}",
                f"提交人：{reporter.display_name}",
                f"提交时间：{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
                "",
                "问题描述：",
                description,
                "",
                f"图片数量：{len(files)}",
            ]
        )
    )

    for index, evidence in enumerate(files, start=1):
        path = Path(evidence.stored_path)
        if not path.exists():
            raise RuntimeError(f"第 {index} 张反馈图片已丢失")
        maintype, subtype = evidence.content_type.split("/", 1)
        message.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=evidence.original_name or f"bug-image-{index}",
        )

    _send_message(message)


def send_smtp_test_email(admin: User) -> None:
    settings = get_settings()
    _require_email_config(settings)
    message = EmailMessage()
    message["Subject"] = "[辅料称重防错系统] SMTP 测试邮件"
    message["From"] = formataddr(("牧衡辅料称重防错系统", settings.smtp_username))
    message["To"] = settings.bug_report_recipient
    message["Date"] = format_datetime(datetime.now().astimezone())
    message.set_content(
        "\n".join(
            [
                "这是一封由管理员手动触发的 SMTP 测试邮件。",
                "",
                f"管理员账号：{admin.username}",
                f"管理员姓名：{admin.display_name}",
                f"测试时间：{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            ]
        )
    )
    _send_message(message)


def _image_ids(report: BugReport) -> list[str]:
    try:
        values = json.loads(report.image_file_ids_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def _load_report_files(db: Session, report: BugReport) -> list[EvidenceFile]:
    image_ids = _image_ids(report)
    if not image_ids:
        return []
    records = db.scalars(
        select(EvidenceFile).where(
            EvidenceFile.file_id.in_(image_ids),
            EvidenceFile.uploaded_by == report.reporter_id,
        )
    ).all()
    by_id = {item.file_id: item for item in records}
    missing = [file_id for file_id in image_ids if file_id not in by_id]
    if missing:
        raise RuntimeError("反馈图片不存在或已丢失")
    return [by_id[file_id] for file_id in image_ids]


def recover_interrupted_bug_report_retries() -> None:
    from app.db.session import SessionLocal

    with SessionLocal.begin() as db:
        db.execute(
            update(BugReport)
            .where(BugReport.status == "sending")
            .values(
                status="failed",
                error_message="上一次邮件重试被中断，请重新重试",
            )
        )


@router.get("")
def list_bug_reports(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=200),
) -> dict:
    reports = db.scalars(
        select(BugReport)
        .order_by(BugReport.created_at.desc(), BugReport.id.desc())
        .limit(limit)
    ).all()
    reporter_ids = {report.reporter_id for report in reports}
    reporters = {
        user.id: user
        for user in db.scalars(select(User).where(User.id.in_(reporter_ids))).all()
    } if reporter_ids else {}
    return {
        "items": [
            {
                "id": report.id,
                "source": report.source,
                "reporter_id": report.reporter_id,
                "reporter_username": reporters.get(report.reporter_id).username if reporters.get(report.reporter_id) else None,
                "reporter_name": reporters.get(report.reporter_id).display_name if reporters.get(report.reporter_id) else None,
                "description": report.description,
                "image_count": len(_image_ids(report)),
                "status": report.status,
                "error_message": report.error_message,
                "created_at": report.created_at.isoformat(),
                "sent_at": report.sent_at.isoformat() if report.sent_at else None,
            }
            for report in reports
        ]
    }


@router.post("/smtp-test")
def test_smtp_service(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        send_smtp_test_email(admin)
    except BugReportEmailConfigurationError as exc:
        write_audit(
            db,
            actor_id=admin.id,
            action="bug_report.smtp_test_failed",
            resource_type="bug_report",
            result="failure",
            detail={"error": _safe_error(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={"code": "BUG_REPORT_EMAIL_NOT_CONFIGURED", "message": "反馈邮件服务尚未配置"},
        ) from exc
    except Exception as exc:
        write_audit(
            db,
            actor_id=admin.id,
            action="bug_report.smtp_test_failed",
            resource_type="bug_report",
            result="failure",
            detail={"error": _safe_error(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"code": "SMTP_TEST_FAILED", "message": "SMTP 测试邮件发送失败"},
        ) from exc

    write_audit(
        db,
        actor_id=admin.id,
        action="bug_report.smtp_test_sent",
        resource_type="bug_report",
    )
    db.commit()
    return {"status": "sent", "message": "SMTP 测试邮件已提交"}


@router.post("/{report_id}/retry")
def retry_bug_report(
    report_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    report = db.get(BugReport, report_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "BUG_REPORT_NOT_FOUND", "message": "反馈记录不存在"},
        )
    if report.status == "sent":
        return {"id": report.id, "status": "sent", "message": "该反馈邮件已发送"}
    if report.status == "sending":
        raise HTTPException(
            status_code=409,
            detail={"code": "BUG_REPORT_RETRY_IN_PROGRESS", "message": "该反馈正在重试发送"},
        )

    claim = db.execute(
        update(BugReport)
        .where(
            BugReport.id == report_id,
            BugReport.status.in_(("failed", "pending")),
        )
        .values(status="sending", error_message=None)
    )
    db.commit()
    if claim.rowcount != 1:
        current = db.get(BugReport, report_id)
        if current is not None and current.status == "sent":
            return {"id": current.id, "status": "sent", "message": "该反馈邮件已发送"}
        raise HTTPException(
            status_code=409,
            detail={"code": "BUG_REPORT_RETRY_IN_PROGRESS", "message": "该反馈正在重试发送"},
        )

    reporter = db.get(User, report.reporter_id)
    if reporter is None:
        error_message = "反馈提交账号不存在"
        report = db.get(BugReport, report_id)
        if report is not None:
            report.status = "failed"
            report.error_message = error_message
        db.commit()
        raise HTTPException(
            status_code=409,
            detail={"code": "BUG_REPORT_REPORTER_MISSING", "message": error_message},
        )

    try:
        files = _load_report_files(db, report)
        send_bug_report_email(
            reporter=reporter,
            source=report.source,
            description=report.description,
            files=files,
        )
    except BugReportEmailConfigurationError as exc:
        error_message = _safe_error(exc)
        report.status = "failed"
        report.error_message = error_message
        write_audit(
            db,
            actor_id=admin.id,
            action="bug_report.retry_failed",
            resource_type="bug_report",
            resource_id=report.id,
            result="failure",
            detail={"error": error_message},
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={"code": "BUG_REPORT_EMAIL_NOT_CONFIGURED", "message": "反馈邮件服务尚未配置"},
        ) from exc
    except Exception as exc:
        error_message = _safe_error(exc)
        report.status = "failed"
        report.error_message = error_message
        write_audit(
            db,
            actor_id=admin.id,
            action="bug_report.retry_failed",
            resource_type="bug_report",
            resource_id=report.id,
            result="failure",
            detail={"error": error_message},
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"code": "BUG_REPORT_RETRY_FAILED", "message": "反馈邮件重试失败"},
        ) from exc

    report.status = "sent"
    report.error_message = None
    report.sent_at = datetime.now(timezone.utc)
    write_audit(
        db,
        actor_id=admin.id,
        action="bug_report.retry_sent",
        resource_type="bug_report",
        resource_id=report.id,
        detail={"image_count": len(files)},
    )
    db.commit()
    return {"id": report.id, "status": "sent", "message": "反馈邮件重试成功"}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_bug_report(
    body: BugReportCreate,
    reporter: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    description = body.description.strip()
    if not description:
        raise HTTPException(
            status_code=422,
            detail={"code": "BUG_DESCRIPTION_REQUIRED", "message": "请填写问题描述"},
        )
    if len(set(body.image_file_ids)) != len(body.image_file_ids):
        raise HTTPException(
            status_code=422,
            detail={"code": "DUPLICATE_BUG_IMAGE", "message": "反馈图片不能重复"},
        )

    files: list[EvidenceFile] = []
    if body.image_file_ids:
        records = db.scalars(
            select(EvidenceFile).where(
                EvidenceFile.file_id.in_(body.image_file_ids),
                EvidenceFile.uploaded_by == reporter.id,
            )
        ).all()
        by_id = {item.file_id: item for item in records}
        missing = [file_id for file_id in body.image_file_ids if file_id not in by_id]
        if missing:
            raise HTTPException(
                status_code=422,
                detail={"code": "BUG_IMAGE_NOT_FOUND", "message": "反馈图片不存在或不属于当前账号"},
            )
        files = [by_id[file_id] for file_id in body.image_file_ids]

    report = BugReport(
        reporter_id=reporter.id,
        source=body.source,
        description=description,
        image_file_ids_json=json.dumps(body.image_file_ids, ensure_ascii=False),
        status="pending",
    )
    db.add(report)
    db.flush()

    try:
        send_bug_report_email(
            reporter=reporter,
            source=body.source,
            description=description,
            files=files,
        )
    except BugReportEmailConfigurationError as exc:
        report.status = "failed"
        report.error_message = _safe_error(exc)
        write_audit(
            db,
            actor_id=reporter.id,
            action="bug_report.email_not_configured",
            resource_type="bug_report",
            resource_id=report.id,
            result="failure",
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={"code": "BUG_REPORT_EMAIL_NOT_CONFIGURED", "message": "反馈邮件服务尚未配置，请联系系统维护人员"},
        ) from exc
    except Exception as exc:
        report.status = "failed"
        report.error_message = _safe_error(exc)
        write_audit(
            db,
            actor_id=reporter.id,
            action="bug_report.email_failed",
            resource_type="bug_report",
            resource_id=report.id,
            result="failure",
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"code": "BUG_REPORT_EMAIL_FAILED", "message": "反馈邮件发送失败，请稍后重试"},
        ) from exc

    report.status = "sent"
    report.sent_at = datetime.now(timezone.utc)
    write_audit(
        db,
        actor_id=reporter.id,
        action="bug_report.sent",
        resource_type="bug_report",
        resource_id=report.id,
        detail={"source": body.source, "image_count": len(files)},
    )
    db.commit()
    return {"id": report.id, "status": "sent", "message": "BUG 反馈已提交"}

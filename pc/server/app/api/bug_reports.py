import json
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, format_datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import get_settings
from app.db.models import AuditLog, BugReport, EvidenceFile, User
from app.db.session import get_db


router = APIRouter(prefix="/bug-reports", tags=["bug-reports"])
MAX_BUG_IMAGES = 8


class BugReportCreate(BaseModel):
    source: Literal["pc", "app"]
    description: str = Field(min_length=1, max_length=5000)
    image_file_ids: list[str] = Field(default_factory=list, max_length=MAX_BUG_IMAGES)


class BugReportEmailConfigurationError(RuntimeError):
    pass


def send_bug_report_email(
    *,
    reporter: User,
    source: str,
    description: str,
    files: list[EvidenceFile],
) -> None:
    settings = get_settings()
    if not settings.smtp_username or not settings.smtp_password:
        raise BugReportEmailConfigurationError("邮件发送服务尚未配置")

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
        report.error_message = str(exc)
        db.add(
            AuditLog(
                actor_id=reporter.id,
                action="bug_report.email_not_configured",
                resource_type="bug_report",
                resource_id=str(report.id),
                detail_json=None,
            )
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail={"code": "BUG_REPORT_EMAIL_NOT_CONFIGURED", "message": "反馈邮件服务尚未配置，请联系系统维护人员"},
        ) from exc
    except Exception as exc:
        report.status = "failed"
        report.error_message = str(exc)[:1000]
        db.add(
            AuditLog(
                actor_id=reporter.id,
                action="bug_report.email_failed",
                resource_type="bug_report",
                resource_id=str(report.id),
                detail_json=None,
            )
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={"code": "BUG_REPORT_EMAIL_FAILED", "message": "反馈邮件发送失败，请稍后重试"},
        ) from exc

    report.status = "sent"
    report.sent_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            actor_id=reporter.id,
            action="bug_report.sent",
            resource_type="bug_report",
            resource_id=str(report.id),
            detail_json=json.dumps({"source": body.source, "image_count": len(files)}, separators=(",", ":")),
        )
    )
    db.commit()
    return {"id": report.id, "status": "sent", "message": "BUG 反馈已提交"}

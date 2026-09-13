def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class FakeSMTP:
    sent_messages = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def login(self, username, password):
        self.username = username
        self.password = password

    def send_message(self, message):
        self.sent_messages.append(message)


class FailingSMTP(FakeSMTP):
    def send_message(self, message):
        raise RuntimeError("bad credential smtp-authorization-code")


def test_bug_report_sends_text_and_multiple_images_to_fixed_recipient(client, monkeypatch):
    from app.core.config import get_settings

    headers = admin_headers(client)
    first = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("screen-1.jpg", b"first-image", "image/jpeg")},
    ).json()["file_id"]
    second = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("screen-2.png", b"second-image", "image/png")},
    ).json()["file_id"]

    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", "sender@qq.com")
    monkeypatch.setattr(settings, "smtp_password", "smtp-authorization-code")
    FakeSMTP.sent_messages = []
    monkeypatch.setattr("app.api.bug_reports.smtplib.SMTP_SSL", FakeSMTP)

    response = client.post(
        "/api/v1/bug-reports",
        headers=headers,
        json={
            "source": "pc",
            "description": "审批中心点击批准后页面没有刷新",
            "image_file_ids": [first, second],
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "sent"
    assert len(FakeSMTP.sent_messages) == 1
    message = FakeSMTP.sent_messages[0]
    assert message["To"] == "1218740205@qq.com"
    assert "审批中心点击批准后页面没有刷新" in message.get_body(preferencelist=("plain",)).get_content()
    attachments = [part for part in message.iter_attachments()]
    assert len(attachments) == 2
    assert attachments[0].get_filename() == "screen-1.jpg"
    assert attachments[1].get_filename() == "screen-2.png"


def test_bug_report_returns_clear_error_when_email_is_not_configured(client, monkeypatch):
    from app.core.config import get_settings
    from app.db.models import BugReport
    from app.db.session import SessionLocal

    headers = admin_headers(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)

    response = client.post(
        "/api/v1/bug-reports",
        headers=headers,
        json={"source": "app", "description": "平板端无法提交反馈", "image_file_ids": []},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "BUG_REPORT_EMAIL_NOT_CONFIGURED"
    with SessionLocal() as db:
        report = db.query(BugReport).order_by(BugReport.id.desc()).first()
        assert report is not None
        assert report.status == "failed"
        assert report.source == "app"


def test_bug_report_rejects_images_uploaded_by_another_user(client):
    admin = admin_headers(client)
    file_id = client.post(
        "/api/v1/evidence/files",
        headers=admin,
        files={"file": ("admin-image.jpg", b"image", "image/jpeg")},
    ).json()["file_id"]
    created = client.post(
        "/api/v1/auth/users",
        headers=admin,
        json={"username": "operator1", "display_name": "操作员一", "password": "password123", "employee_no": "MH1001"},
    ).json()["user"]
    operator_token = client.post(
        "/api/v1/auth/login",
        json={"username": created["username"], "password": "password123"},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/bug-reports",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"source": "app", "description": "引用其他账号图片", "image_file_ids": [file_id]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "BUG_IMAGE_NOT_FOUND"


def test_admin_lists_bug_reports_and_operator_is_denied(client, monkeypatch):
    from app.core.config import get_settings

    headers = admin_headers(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", "sender@qq.com")
    monkeypatch.setattr(settings, "smtp_password", "smtp-authorization-code")
    FakeSMTP.sent_messages = []
    monkeypatch.setattr("app.api.bug_reports.smtplib.SMTP_SSL", FakeSMTP)

    created = client.post(
        "/api/v1/bug-reports",
        headers=headers,
        json={"source": "pc", "description": "审批中心红点未消失", "image_file_ids": []},
    )
    assert created.status_code == 201

    response = client.get("/api/v1/bug-reports", headers=headers)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["description"] == "审批中心红点未消失"
    assert item["status"] == "sent"
    assert item["reporter_username"] == "admin"

    operator = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": "bug-operator",
            "display_name": "反馈操作员",
            "password": "password123",
            "employee_no": "MH9001",
        },
    ).json()["user"]
    operator_token = client.post(
        "/api/v1/auth/login",
        json={"username": operator["username"], "password": "password123"},
    ).json()["access_token"]
    operator_headers = {"Authorization": f"Bearer {operator_token}"}

    assert client.get("/api/v1/bug-reports", headers=operator_headers).status_code == 403
    assert client.post("/api/v1/bug-reports/smtp-test", headers=operator_headers).status_code == 403
    assert (
        client.post(
            f"/api/v1/bug-reports/{item['id']}/retry",
            headers=operator_headers,
        ).status_code
        == 403
    )


def test_admin_sends_smtp_test_to_fixed_recipient(client, monkeypatch):
    from app.core.config import get_settings

    headers = admin_headers(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", "sender@qq.com")
    monkeypatch.setattr(settings, "smtp_password", "smtp-authorization-code")
    FakeSMTP.sent_messages = []
    monkeypatch.setattr("app.api.bug_reports.smtplib.SMTP_SSL", FakeSMTP)

    response = client.post("/api/v1/bug-reports/smtp-test", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert len(FakeSMTP.sent_messages) == 1
    assert FakeSMTP.sent_messages[0]["To"] == "1218740205@qq.com"


def test_admin_retries_failed_bug_report_once(client, monkeypatch):
    from app.core.config import get_settings
    from app.db.models import BugReport
    from app.db.session import SessionLocal

    headers = admin_headers(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    created = client.post(
        "/api/v1/bug-reports",
        headers=headers,
        json={"source": "app", "description": "平板拍照偶发失败", "image_file_ids": []},
    )
    assert created.status_code == 503

    with SessionLocal() as db:
        report = db.query(BugReport).order_by(BugReport.id.desc()).first()
        assert report is not None
        report_id = report.id
        assert report.status == "failed"

    monkeypatch.setattr(settings, "smtp_username", "sender@qq.com")
    monkeypatch.setattr(settings, "smtp_password", "smtp-authorization-code")
    FakeSMTP.sent_messages = []
    monkeypatch.setattr("app.api.bug_reports.smtplib.SMTP_SSL", FakeSMTP)

    response = client.post(f"/api/v1/bug-reports/{report_id}/retry", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert len(FakeSMTP.sent_messages) == 1

    repeated = client.post(f"/api/v1/bug-reports/{report_id}/retry", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "sent"
    assert len(FakeSMTP.sent_messages) == 1

    with SessionLocal() as db:
        report = db.get(BugReport, report_id)
        assert report is not None
        assert report.status == "sent"
        assert report.sent_at is not None


def test_retry_failure_redacts_smtp_authorization_code(client, monkeypatch):
    from app.core.config import get_settings
    from app.db.models import BugReport
    from app.db.session import SessionLocal

    headers = admin_headers(client)
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    created = client.post(
        "/api/v1/bug-reports",
        headers=headers,
        json={"source": "pc", "description": "导出失败", "image_file_ids": []},
    )
    assert created.status_code == 503

    with SessionLocal() as db:
        report_id = db.query(BugReport).order_by(BugReport.id.desc()).first().id

    monkeypatch.setattr(settings, "smtp_username", "sender@qq.com")
    monkeypatch.setattr(settings, "smtp_password", "smtp-authorization-code")
    monkeypatch.setattr("app.api.bug_reports.smtplib.SMTP_SSL", FailingSMTP)

    response = client.post(f"/api/v1/bug-reports/{report_id}/retry", headers=headers)
    assert response.status_code == 502

    with SessionLocal() as db:
        report = db.get(BugReport, report_id)
        assert report is not None
        assert report.status == "failed"
        assert "smtp-authorization-code" not in (report.error_message or "")
        assert "[REDACTED]" in (report.error_message or "")


def test_retry_fails_when_original_image_is_missing(client, monkeypatch):
    from app.core.config import get_settings
    from app.db.models import BugReport, EvidenceFile
    from app.db.session import SessionLocal

    headers = admin_headers(client)
    uploaded = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("feedback.png", b"feedback-image", "image/png")},
    ).json()["file_id"]
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    created = client.post(
        "/api/v1/bug-reports",
        headers=headers,
        json={"source": "pc", "description": "带图片的反馈", "image_file_ids": [uploaded]},
    )
    assert created.status_code == 503

    with SessionLocal.begin() as db:
        report_id = db.query(BugReport).order_by(BugReport.id.desc()).first().id
        evidence = db.query(EvidenceFile).filter(EvidenceFile.file_id == uploaded).one()
        db.delete(evidence)

    monkeypatch.setattr(settings, "smtp_username", "sender@qq.com")
    monkeypatch.setattr(settings, "smtp_password", "smtp-authorization-code")
    FakeSMTP.sent_messages = []
    monkeypatch.setattr("app.api.bug_reports.smtplib.SMTP_SSL", FakeSMTP)

    response = client.post(f"/api/v1/bug-reports/{report_id}/retry", headers=headers)

    assert response.status_code == 502
    assert FakeSMTP.sent_messages == []
    with SessionLocal() as db:
        report = db.get(BugReport, report_id)
        assert report is not None
        assert report.status == "failed"
        assert "反馈图片不存在或已丢失" in (report.error_message or "")

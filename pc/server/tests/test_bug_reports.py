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
        json={"username": "operator1", "display_name": "操作员一", "password": "password123"},
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

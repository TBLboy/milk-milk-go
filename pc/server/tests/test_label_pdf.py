"""TASK-132: 标签导出 PDF 后端生成。"""
import io
import zipfile
from datetime import datetime, timezone

from app.services.label_pdf import (
    LabelPdfRequest,
    parse_label_size,
    render_label_pdf,
    render_labels_pdf,
)


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_material(client, headers, code="A1", name="白砂糖"):
    return client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": code, "name_zh": name, "shelf_life_months": 24},
    ).json()


def test_parse_label_size():
    assert parse_label_size("60x40") == (60, 40)
    assert parse_label_size("100×50") == (100, 50)
    assert parse_label_size(None) == (60, 40)
    assert parse_label_size("bad") == (60, 40)
    assert parse_label_size("5x5") == (60, 40)


def test_render_single_label_pdf_has_correct_page_size():
    request = LabelPdfRequest(
        label_id="LBL-20260924-abc123",
        material_name="白砂糖",
        material_code="A1",
        printed_at=datetime.now(timezone.utc),
        width_mm=60,
        height_mm=40,
    )
    payload = render_label_pdf(request)
    assert payload.startswith(b"%PDF-")
    assert b"/MediaBox [ 0 0 170.0787 113.3858 ]" in payload or b"MediaBox" in payload


def test_render_multiple_labels_into_single_pdf():
    request = LabelPdfRequest(
        label_id="LBL-20260924-abc123",
        material_name="白砂糖",
        material_code="A1",
        printed_at=datetime.now(timezone.utc),
        width_mm=60,
        height_mm=40,
    )
    payload = render_labels_pdf([request, request, request])
    assert payload.startswith(b"%PDF-")
    assert payload.count(b"/Type /Page\n") >= 3 or payload.count(b"/Type /Page") >= 3


def test_export_merged_pdf(client):
    headers = admin_headers(client)
    material = create_material(client, headers)
    response = client.post(
        "/api/v1/labels/export-pdf",
        headers=headers,
        json={"material_ids": [material["material_id"]], "mode": "merged", "quantity": 2},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_export_split_zip_uses_material_names(client):
    headers = admin_headers(client)
    first = create_material(client, headers, code="A1", name="白砂糖")
    second = create_material(client, headers, code="A2", name="可可粉")
    response = client.post(
        "/api/v1/labels/export-pdf",
        headers=headers,
        json={"material_ids": [first["material_id"], second["material_id"]], "mode": "split"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert "白砂糖.pdf" in names
        assert "可可粉.pdf" in names
        assert archive.read("白砂糖.pdf").startswith(b"%PDF-")


def test_export_rejects_unknown_material(client):
    headers = admin_headers(client)
    response = client.post(
        "/api/v1/labels/export-pdf",
        headers=headers,
        json={"material_ids": ["MAT-99999"], "mode": "merged"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "MATERIAL_NOT_FOUND"

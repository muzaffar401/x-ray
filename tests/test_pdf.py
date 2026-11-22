# Tests for PDF export generation, approval requirement, and audit integration.
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import AuditLog, User
from app.security import hash_password


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if not db.query(User).filter(User.username == "pdf_doctor").first():
        db.add(User(username="pdf_doctor", password_hash=hash_password("DoctorPass123"), role="doctor"))

    db.commit()
    db.close()
    yield


@pytest.fixture
def auth_client():
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"username": "pdf_doctor", "password": "DoctorPass123"})
    assert res.status_code == 200
    return client


def make_test_png() -> bytes:
    img = Image.new("L", (120, 120), color=100)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_pdf_export_unapproved_draft_returns_409(auth_client):
    png_bytes = make_test_png()
    post_res = auth_client.post("/api/reports", files={"file": ("draft.png", png_bytes, "image/png")})
    assert post_res.status_code == 201
    report_id = post_res.json()["id"]

    # Attempt PDF export while report is still draft -> 409 Conflict
    pdf_res = auth_client.get(f"/api/reports/{report_id}/pdf")
    assert pdf_res.status_code == 409
    assert "PDF export is available only for approved reports" in pdf_res.json()["detail"]


def test_pdf_export_approved_report_succeeds(auth_client):
    png_bytes = make_test_png()
    post_res = auth_client.post("/api/reports", files={"file": ("approved_scan.png", png_bytes, "image/png")})
    report_id = post_res.json()["id"]

    # Approve report
    app_res = auth_client.post(f"/api/reports/{report_id}/approve")
    assert app_res.status_code == 200

    # Request PDF export
    pdf_res = auth_client.get(f"/api/reports/{report_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")
    assert len(pdf_res.content) > 1000  # Valid generated binary PDF


def test_pdf_export_records_audit_log(auth_client):
    png_bytes = make_test_png()
    post_res = auth_client.post("/api/reports", files={"file": ("audit_pdf.png", png_bytes, "image/png")})
    report_id = post_res.json()["id"]
    auth_client.post(f"/api/reports/{report_id}/approve")

    # Export PDF
    pdf_res = auth_client.get(f"/api/reports/{report_id}/pdf")
    assert pdf_res.status_code == 200

    # Verify audit log entry
    db = SessionLocal()
    entry = (
        db.query(AuditLog)
        .filter(AuditLog.report_id == report_id, AuditLog.action == "pdf_exported")
        .first()
    )
    assert entry is not None
    assert entry.action == "pdf_exported"
    assert "PDF exported" in entry.details
    db.close()


def test_pdf_export_unauthenticated_returns_401():
    anon = TestClient(app)
    res = anon.get("/api/reports/1/pdf")
    assert res.status_code == 401

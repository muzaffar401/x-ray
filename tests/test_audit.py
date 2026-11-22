# Tests for audit logging functionality and administrative access controls.
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import AuditLog, User
from app.security import hash_password
from app.services.audit import log_action


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Create admin user
    if not db.query(User).filter(User.username == "audit_admin").first():
        db.add(User(username="audit_admin", password_hash=hash_password("AdminPass123"), role="admin"))

    # Create doctor user
    if not db.query(User).filter(User.username == "audit_doctor").first():
        db.add(User(username="audit_doctor", password_hash=hash_password("DoctorPass123"), role="doctor"))

    db.commit()
    db.close()
    yield


@pytest.fixture
def admin_client():
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"username": "audit_admin", "password": "AdminPass123"})
    assert res.status_code == 200
    return client


@pytest.fixture
def doctor_client():
    client = TestClient(app)
    res = client.post("/api/auth/login", json={"username": "audit_doctor", "password": "DoctorPass123"})
    assert res.status_code == 200
    return client


def make_test_png() -> bytes:
    img = Image.new("L", (100, 100), color=120)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_log_action_helper_persists_valid_entry():
    db = SessionLocal()
    entry = log_action(db, action="login", user_id=1, details="Admin login from test")
    assert entry.id is not None
    assert entry.action == "login"
    assert entry.user_id == 1
    assert entry.details == "Admin login from test"
    db.close()


def test_log_action_invalid_action_rejected():
    db = SessionLocal()
    with pytest.raises(ValueError, match="Invalid audit action"):
        log_action(db, action="hacked_system", details="illegal")
    db.close()


def test_audit_api_requires_admin(admin_client, doctor_client):
    # Unauthenticated -> 401
    anon_client = TestClient(app)
    unauth_res = anon_client.get("/api/audit")
    assert unauth_res.status_code == 401

    # Doctor -> 403 Forbidden
    doc_res = doctor_client.get("/api/audit")
    assert doc_res.status_code == 403
    assert "Admin privileges required" in doc_res.json()["detail"]

    # Admin -> 200 OK
    admin_res = admin_client.get("/api/audit")
    assert admin_res.status_code == 200
    logs = admin_res.json()
    assert isinstance(logs, list)
    assert len(logs) > 0


def test_full_lifecycle_actions_are_audited(doctor_client, admin_client):
    # 1. Login failed event
    anon = TestClient(app)
    anon.post("/api/auth/login", json={"username": "audit_doctor", "password": "WrongPassword"})

    # 2. Report created
    png_bytes = make_test_png()
    upload_res = doctor_client.post("/api/reports", files={"file": ("scan.png", png_bytes, "image/png")})
    assert upload_res.status_code == 201
    report_id = upload_res.json()["id"]

    # 3. Report viewed
    view_res = doctor_client.get(f"/api/reports/{report_id}")
    assert view_res.status_code == 200

    # 4. Report edited
    edit_res = doctor_client.put(
        f"/api/reports/{report_id}",
        json={"final_findings": "Updated findings", "final_impression": "Updated impression"},
    )
    assert edit_res.status_code == 200

    # 5. Report approved
    approve_res = doctor_client.post(f"/api/reports/{report_id}/approve")
    assert approve_res.status_code == 200

    # Query audit logs as admin
    audit_res = admin_client.get("/api/audit")
    assert audit_res.status_code == 200
    actions = [item["action"] for item in audit_res.json()]

    assert "login_failed" in actions
    assert "created" in actions
    assert "viewed" in actions
    assert "edited" in actions
    assert "approved" in actions

    # Verify no patient information or full report findings are stored in audit details
    for item in audit_res.json():
        assert "Updated findings" not in (item["details"] or "")
        assert "[MOCK SAMPLE" not in (item["details"] or "")

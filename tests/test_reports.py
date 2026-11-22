# Tests for reports REST API endpoints with authentication and permission checks.
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Ensure dr_one exists
    if not db.query(User).filter(User.username == "dr_one").first():
        db.add(User(username="dr_one", password_hash=hash_password("DoctorPass1"), role="doctor"))

    # Ensure dr_two exists (for permission checks)
    if not db.query(User).filter(User.username == "dr_two").first():
        db.add(User(username="dr_two", password_hash=hash_password("DoctorPass2"), role="doctor"))

    # Ensure admin user exists
    if not db.query(User).filter(User.username == "admin_user").first():
        db.add(User(username="admin_user", password_hash=hash_password("AdminPass123"), role="admin"))

    db.commit()
    db.close()
    yield


@pytest.fixture
def auth_client():
    client = TestClient(app)
    # Log in as dr_one by default
    res = client.post("/api/auth/login", json={"username": "dr_one", "password": "DoctorPass1"})
    assert res.status_code == 200
    return client


@pytest.fixture
def other_doctor_client():
    client = TestClient(app)
    # Log in as dr_two
    res = client.post("/api/auth/login", json={"username": "dr_two", "password": "DoctorPass2"})
    assert res.status_code == 200
    return client


@pytest.fixture
def admin_client():
    client = TestClient(app)
    # Log in as admin
    res = client.post("/api/auth/login", json={"username": "admin_user", "password": "AdminPass123"})
    assert res.status_code == 200
    return client


def make_test_image_bytes(fmt: str = "PNG", size: tuple[int, int] = (120, 120)) -> bytes:
    img = Image.new("RGB", size, color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_unauthenticated_request_rejected():
    anon_client = TestClient(app)
    res = anon_client.get("/api/reports")
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]


def test_upload_valid_image(auth_client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("chest_sample.png", img_bytes, "image/png")}

    response = auth_client.post("/api/reports", files=files)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "draft"
    assert data["original_filename"] == "chest_sample.png"
    assert data["is_mock"] is True
    assert data["ai_findings"].startswith("[MOCK SAMPLE - NOT A REAL ANALYSIS]")
    assert data["final_findings"] == data["ai_findings"]
    assert data["final_impression"] == data["ai_impression"]
    assert data["created_by"] is not None
    assert "chest_sample.png" not in data["image_path"]
    assert data["image_path"].endswith(".png")


def test_upload_bad_file_rejected(auth_client):
    files = {"file": ("malicious.png", b"not-a-real-image", "image/png")}
    response = auth_client.post("/api/reports", files=files)
    assert response.status_code == 400
    assert "Corrupted or invalid PNG image content" in response.json()["detail"]


def test_list_and_get_single_report(auth_client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("scan1.png", img_bytes, "image/png")}
    post_res = auth_client.post("/api/reports", files=files)
    assert post_res.status_code == 201
    report_id = post_res.json()["id"]

    list_res = auth_client.get("/api/reports")
    assert list_res.status_code == 200
    reports = list_res.json()
    assert len(reports) >= 1
    assert reports[0]["id"] == report_id

    get_res = auth_client.get(f"/api/reports/{report_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == report_id


def test_get_report_image(auth_client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("xray_view.png", img_bytes, "image/png")}
    post_res = auth_client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    img_res = auth_client.get(f"/api/reports/{report_id}/image")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 0


def test_edit_draft_report_by_creator(auth_client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("edit_sample.png", img_bytes, "image/png")}
    post_res = auth_client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    update_payload = {
        "final_findings": "Doctor revised: Mild interstitial prominence noted at right base.",
        "final_impression": "Doctor revised: Follow-up in 4 weeks recommended.",
    }

    put_res = auth_client.put(f"/api/reports/{report_id}", json=update_payload)
    assert put_res.status_code == 200
    updated_data = put_res.json()
    assert updated_data["final_findings"] == update_payload["final_findings"]
    assert updated_data["final_impression"] == update_payload["final_impression"]
    assert updated_data["status"] == "draft"


def test_other_doctor_cannot_edit_or_approve_report(auth_client, other_doctor_client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("doctor_one_report.png", img_bytes, "image/png")}
    post_res = auth_client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    # Dr. Two attempts to edit Dr. One's report -> 403 Forbidden
    edit_payload = {"final_findings": "Unauthorized edit", "final_impression": "Should fail"}
    edit_res = other_doctor_client.put(f"/api/reports/{report_id}", json=edit_payload)
    assert edit_res.status_code == 403
    assert "do not have permission" in edit_res.json()["detail"]

    # Dr. Two attempts to approve Dr. One's report -> 403 Forbidden
    approve_res = other_doctor_client.post(f"/api/reports/{report_id}/approve")
    assert approve_res.status_code == 403
    assert "do not have permission" in approve_res.json()["detail"]


def test_admin_can_edit_and_approve_any_report(auth_client, admin_client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("doctor_report.png", img_bytes, "image/png")}
    post_res = auth_client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    # Admin edits report created by doctor
    admin_edit = {"final_findings": "Admin review applied", "final_impression": "Admin approved"}
    edit_res = admin_client.put(f"/api/reports/{report_id}", json=admin_edit)
    assert edit_res.status_code == 200

    # Admin approves report
    app_res = admin_client.post(f"/api/reports/{report_id}/approve")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"


def test_approve_report_and_block_subsequent_edits(auth_client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("approve_sample.png", img_bytes, "image/png")}
    post_res = auth_client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    # 1. Approve report
    approve_res = auth_client.post(f"/api/reports/{report_id}/approve")
    assert approve_res.status_code == 200
    approved_data = approve_res.json()
    assert approved_data["status"] == "approved"
    assert approved_data["approved_at"] is not None

    # 2. Attempt edit after approval -> must return 409 Conflict
    forbidden_edit_payload = {
        "final_findings": "Attempting changes after approval",
        "final_impression": "Should fail",
    }
    blocked_res = auth_client.put(f"/api/reports/{report_id}", json=forbidden_edit_payload)
    assert blocked_res.status_code == 409
    assert "already been approved" in blocked_res.json()["detail"]

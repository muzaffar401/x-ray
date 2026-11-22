# Tests for reports REST API endpoints.
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.db import Base, engine


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def make_test_image_bytes(fmt: str = "PNG", size: tuple[int, int] = (120, 120)) -> bytes:
    img = Image.new("RGB", size, color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_upload_valid_image(client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("chest_sample.png", img_bytes, "image/png")}

    response = client.post("/api/reports", files=files)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "draft"
    assert data["original_filename"] == "chest_sample.png"
    assert data["is_mock"] is True
    assert data["ai_findings"].startswith("[MOCK SAMPLE - NOT A REAL ANALYSIS]")
    assert data["final_findings"] == data["ai_findings"]
    assert data["final_impression"] == data["ai_impression"]
    assert "chest_sample.png" not in data["image_path"]  # Stored with random UUID filename
    assert data["image_path"].endswith(".png")


def test_upload_bad_file_rejected(client):
    # Text file masquerading as image
    files = {"file": ("malicious.png", b"not-a-real-image", "image/png")}
    response = client.post("/api/reports", files=files)
    assert response.status_code == 400
    assert "Corrupted or invalid PNG image content" in response.json()["detail"]


def test_list_and_get_single_report(client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("scan1.png", img_bytes, "image/png")}
    post_res = client.post("/api/reports", files=files)
    assert post_res.status_code == 201
    report_id = post_res.json()["id"]

    # List reports
    list_res = client.get("/api/reports")
    assert list_res.status_code == 200
    reports = list_res.json()
    assert len(reports) >= 1
    assert reports[0]["id"] == report_id  # Newest first

    # Get single report
    get_res = client.get(f"/api/reports/{report_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == report_id


def test_get_report_image(client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("xray_view.png", img_bytes, "image/png")}
    post_res = client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    # Fetch saved image
    img_res = client.get(f"/api/reports/{report_id}/image")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"] == "image/png"
    assert len(img_res.content) > 0


def test_edit_draft_report(client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("edit_sample.png", img_bytes, "image/png")}
    post_res = client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    update_payload = {
        "final_findings": "Doctor revised: Mild interstitial prominence noted at right base.",
        "final_impression": "Doctor revised: Follow-up in 4 weeks recommended.",
    }

    put_res = client.put(f"/api/reports/{report_id}", json=update_payload)
    assert put_res.status_code == 200
    updated_data = put_res.json()
    assert updated_data["final_findings"] == update_payload["final_findings"]
    assert updated_data["final_impression"] == update_payload["final_impression"]
    assert updated_data["status"] == "draft"


def test_approve_report_and_block_subsequent_edits(client):
    img_bytes = make_test_image_bytes("PNG")
    files = {"file": ("approve_sample.png", img_bytes, "image/png")}
    post_res = client.post("/api/reports", files=files)
    report_id = post_res.json()["id"]

    # 1. Approve report
    approve_res = client.post(f"/api/reports/{report_id}/approve")
    assert approve_res.status_code == 200
    approved_data = approve_res.json()
    assert approved_data["status"] == "approved"
    assert approved_data["approved_at"] is not None

    # 2. Attempt edit after approval -> must return 409 Conflict
    forbidden_edit_payload = {
        "final_findings": "Attempting changes after approval",
        "final_impression": "Should fail",
    }
    blocked_res = client.put(f"/api/reports/{report_id}", json=forbidden_edit_payload)
    assert blocked_res.status_code == 409
    assert "already been approved" in blocked_res.json()["detail"]

# Unit tests for the standalone model_service FastAPI application.
import io
import os
import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Set mock mode and test key before importing server
os.environ["MOCK_MODEL"] = "1"
os.environ["MODEL_SERVICE_KEY"] = "test-secret-service-key-123"

from model_service.server import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_png_bytes():
    """Create a minimal valid in-memory PNG."""
    img = Image.new("RGB", (64, 64), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_health_endpoint(client: TestClient):
    """GET /health returns 200 and model status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["model_loaded"] is True
    assert "AI-generated DRAFT" in data["disclaimer"]


def test_generate_missing_api_key(client: TestClient, sample_png_bytes: bytes):
    """POST /generate without X-API-Key returns 401."""
    files = {"file": ("test.png", sample_png_bytes, "image/png")}
    res = client.post("/generate", files=files)
    assert res.status_code == 401
    assert "Invalid or missing API key" in res.json()["detail"]


def test_generate_wrong_api_key(client: TestClient, sample_png_bytes: bytes):
    """POST /generate with wrong X-API-Key returns 401."""
    files = {"file": ("test.png", sample_png_bytes, "image/png")}
    headers = {"X-API-Key": "wrong-secret-key"}
    res = client.post("/generate", files=files, headers=headers)
    assert res.status_code == 401
    assert "Invalid or missing API key" in res.json()["detail"]


def test_generate_valid_request(client: TestClient, sample_png_bytes: bytes):
    """POST /generate with valid API key returns report with empty impression."""
    files = {"file": ("test.png", sample_png_bytes, "image/png")}
    headers = {"X-API-Key": "test-secret-service-key-123"}
    res = client.post("/generate", files=files, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "findings" in data
    assert len(data["findings"]) > 10
    # CXR-LLaVA does not produce an impression, so impression must be empty string
    assert data["impression"] == ""
    assert data["model_name"] == "ECOFRI/CXR-LLAVA-v2"
    assert "AI-generated DRAFT" in data["disclaimer"]


def test_generate_invalid_file(client: TestClient):
    """POST /generate with corrupt file returns 400."""
    files = {"file": ("bad.png", b"not a valid image", "image/png")}
    headers = {"X-API-Key": "test-secret-service-key-123"}
    res = client.post("/generate", files=files, headers=headers)
    assert res.status_code == 400
    assert "Invalid or unreadable image file" in res.json()["detail"]

# Tests for report engine interface, mock engine, real engine, and engine factory.
from typing import Any
import pytest
from fastapi import HTTPException
import httpx

from app.services.engines.base import ReportEngine
from app.services.engines.mock import MockEngine
from app.services.engines.real import RealEngine
from app.services.engines import get_engine


def test_cannot_instantiate_abstract_base_engine():
    with pytest.raises(TypeError):
        ReportEngine()  # type: ignore


def test_mock_engine_generates_valid_schema():
    engine = MockEngine()
    result = engine.generate(b"fake_png_bytes")

    assert isinstance(result, dict)
    assert "findings" in result
    assert "impression" in result
    assert "engine_name" in result
    assert "is_mock" in result

    assert isinstance(result["findings"], str)
    assert result["findings"].startswith("[MOCK SAMPLE - NOT A REAL ANALYSIS]")

    assert isinstance(result["impression"], str)
    assert len(result["impression"]) > 0

    assert isinstance(result["engine_name"], str)
    assert result["is_mock"] is True


def test_get_engine_mock(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENGINE", "mock")
    engine = get_engine()
    assert isinstance(engine, MockEngine)
    assert engine.engine_name == "mock-engine-v1"


def test_get_engine_real(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENGINE", "real")
    engine = get_engine()
    assert isinstance(engine, RealEngine)


def test_get_engine_invalid_raises_value_error(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENGINE", "unsupported_xyz")
    with pytest.raises(ValueError, match="Unknown engine type"):
        get_engine()


class MockHttpxResponse:
    def __init__(self, data: dict[str, Any], status_code: int = 200):
        self._data = data
        self.status_code = status_code
        self.is_error = status_code >= 400

    def json(self) -> dict[str, Any]:
        return self._data


def test_real_engine_success_and_headers(monkeypatch):
    captured_kwargs = {}

    def fake_post(self, url, **kwargs):
        nonlocal captured_kwargs
        captured_kwargs = kwargs
        return MockHttpxResponse({
            "findings": "Normal bilateral lungs.",
            "impression": "",
            "model_name": "ECOFRI/CXR-LLAVA-v2"
        })

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    engine = RealEngine(service_url="http://fake-model-service.com", api_key="secret-key-123")
    result = engine.generate(b"sample_png_bytes")

    assert result["findings"] == "Normal bilateral lungs."
    assert result["impression"] == ""
    assert result["engine_name"] == "ECOFRI/CXR-LLAVA-v2"
    assert result["is_mock"] is False

    headers = captured_kwargs.get("headers", {})
    assert headers.get("ngrok-skip-browser-warning") == "1"
    assert headers.get("X-API-Key") == "secret-key-123"


def test_real_engine_503_maps_to_friendly_502(monkeypatch):
    def fake_post(self, url, **kwargs):
        return MockHttpxResponse({"detail": "OOM"}, status_code=503)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    engine = RealEngine(service_url="http://fake-model-service.com", api_key="test-key")
    with pytest.raises(HTTPException) as exc_info:
        engine.generate(b"sample_png")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "The AI model is out of memory or still loading. Try again in a minute."


def test_real_engine_504_maps_to_friendly_502(monkeypatch):
    def fake_post(self, url, **kwargs):
        return MockHttpxResponse({"detail": "Gateway Timeout"}, status_code=504)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    engine = RealEngine(service_url="http://fake-model-service.com", api_key="test-key")
    with pytest.raises(HTTPException) as exc_info:
        engine.generate(b"sample_png")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "The AI model took too long."


def test_real_engine_401_maps_to_friendly_502(monkeypatch):
    def fake_post(self, url, **kwargs):
        return MockHttpxResponse({"detail": "Unauthorized"}, status_code=401)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    engine = RealEngine(service_url="http://fake-model-service.com", api_key="test-key")
    with pytest.raises(HTTPException) as exc_info:
        engine.generate(b"sample_png")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "The model service key is wrong."


def test_real_engine_other_status_maps_to_friendly_502(monkeypatch):
    def fake_post(self, url, **kwargs):
        return MockHttpxResponse({"detail": "Internal Server Error"}, status_code=500)

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    engine = RealEngine(service_url="http://fake-model-service.com", api_key="test-key")
    with pytest.raises(HTTPException) as exc_info:
        engine.generate(b"sample_png")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "The AI model service encountered an unexpected error."


def test_real_engine_timeout_exception_maps_to_friendly_502(monkeypatch):
    def fake_post(self, url, **kwargs):
        raise httpx.ReadTimeout("The read operation timed out")

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    engine = RealEngine(service_url="http://fake-model-service.com", api_key="test-key")
    with pytest.raises(HTTPException) as exc_info:
        engine.generate(b"sample_png")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "The AI model took too long."

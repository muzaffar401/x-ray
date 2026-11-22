# Tests for report engine interface, mock engine, and engine factory.
import pytest
from app.services.engines.base import ReportEngine
from app.services.engines.mock import MockEngine
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


def test_get_engine_real_raises_not_implemented(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENGINE", "real")
    with pytest.raises(NotImplementedError, match="Real engine is added later"):
        get_engine()


def test_get_engine_invalid_raises_value_error(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ENGINE", "unsupported_xyz")
    with pytest.raises(ValueError, match="Unknown engine type"):
        get_engine()

# Inference engine module initialization and factory function.
from app.config import settings
from app.services.engines.base import ReportEngine
from app.services.engines.mock import MockEngine


def get_engine() -> ReportEngine:
    engine_type = settings.ENGINE.lower().strip()
    if engine_type == "mock":
        return MockEngine()
    elif engine_type == "real":
        raise NotImplementedError("Real engine is added later")
    else:
        raise ValueError(f"Unknown engine type '{settings.ENGINE}'. Supported types: 'mock', 'real'.")


__all__ = ["ReportEngine", "MockEngine", "get_engine"]

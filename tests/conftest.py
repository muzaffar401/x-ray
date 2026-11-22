# Global test fixtures ensuring tests run with mock engine and clean test environment.
import os
import pytest

# Ensure tests always default to mock engine
os.environ["ENGINE"] = "mock"
os.environ["MOCK_MODEL"] = "1"
os.environ["MODEL_SERVICE_KEY"] = "test-secret-service-key-123"

from app.config import settings

settings.ENGINE = "mock"

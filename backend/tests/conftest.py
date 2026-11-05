import os
import sys
from pathlib import Path
import pytest

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_external_gemini_in_tests(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")



@pytest.fixture
def client():
    # Set testing environment
    settings.ENVIRONMENT = "development"
    settings.INTERNAL_CRON_SECRET = "test-cron-secret-123"
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def faculty_client():
    settings.ENVIRONMENT = "development"
    settings.INTERNAL_CRON_SECRET = "test-cron-secret-123"
    with TestClient(app, headers={"Authorization": "Bearer dev-faculty"}) as test_client:
        yield test_client


@pytest.fixture
def student_client():
    settings.ENVIRONMENT = "development"
    settings.INTERNAL_CRON_SECRET = "test-cron-secret-123"
    with TestClient(app, headers={"Authorization": "Bearer dev-student"}) as test_client:
        yield test_client

"""Shared fixtures for quiz-app tests."""
import os
import pytest

# Set test environment BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite:///C:/Users/24368/Documents/知识库/quiz-app/backend/tests/test_quiz.db"
os.environ["JWT_SECRET"] = "test-secret-key-for-tests"
os.environ["UVICORN_RELOAD"] = "true"
os.environ["PYTEST_RUNNING"] = "true"

# Import app — its engine now uses the test DB
from app.main import app
from app.db.engine import engine, SessionLocal
from app.db.models import Base
from fastapi.testclient import TestClient

# Create tables on the app's own engine
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Register a test user and return auth headers."""
    client.post("/api/v1/auth/signup", json={
        "username": "testuser", "password": "testpass1234"
    })
    token = client.post("/api/v1/auth/login", json={
        "username": "testuser", "password": "testpass1234"
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

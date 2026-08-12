import os
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/niet_qpg_test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-that-is-long-enough-for-jwt")
os.environ.setdefault("AI_PROVIDER", "local")
os.environ.setdefault("UPLOAD_DIR", "/tmp/niet-qpg-test-uploads")
os.environ.setdefault("GENERATED_DIR", "/tmp/niet-qpg-test-generated")

import pytest
from fastapi.testclient import TestClient

from backend.app.database import Base, engine
from backend.app.main import app


@pytest.fixture(scope="session", autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    for folder in (Path("/tmp/niet-qpg-test-uploads"), Path("/tmp/niet-qpg-test-generated")):
        folder.mkdir(parents=True, exist_ok=True)
        for item in folder.iterdir():
            if item.is_file():
                item.unlink()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def client(clean_database):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_headers(client):
    response = client.post("/api/auth/login", json={"username": "admin@niet.edu", "password": "ChangeMe123!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def teacher_headers(client):
    response = client.post("/api/auth/login", json={"username": "teacher@niet.edu", "password": "Teacher123!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

# Tests for authentication, session management, and brute force protection.
import pytest
from fastapi.testclient import TestClient
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.security import hash_password
from app.routers.auth import FAILED_ATTEMPTS


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    FAILED_ATTEMPTS.clear()
    db = SessionLocal()
    # Create test doctor user
    test_user = db.query(User).filter(User.username == "test_doctor").first()
    if not test_user:
        test_user = User(
            username="test_doctor",
            password_hash=hash_password("DoctorPass123"),
            role="doctor",
            is_active=True,
        )
        db.add(test_user)
        db.commit()
    db.close()
    yield
    FAILED_ATTEMPTS.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_login_successful_and_sets_httponly_cookie(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "test_doctor", "password": "DoctorPass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "test_doctor"
    assert data["role"] == "doctor"

    # Verify cookie
    assert "access_token" in res.cookies
    cookie = res.cookies.get("access_token")
    assert cookie is not None


def test_login_wrong_password_rejected(client):
    res = client.post(
        "/api/auth/login",
        json={"username": "test_doctor", "password": "WrongPassword!"},
    )
    assert res.status_code == 401
    assert "Invalid username or password" in res.json()["detail"]


def test_brute_force_lockout_after_5_failures(client):
    username = "lockout_target"
    db = SessionLocal()
    if not db.query(User).filter(User.username == username).first():
        db.add(User(username=username, password_hash=hash_password("RealPass123"), role="doctor"))
        db.commit()
    db.close()

    # Fail 4 times -> 401
    for i in range(4):
        res = client.post("/api/auth/login", json={"username": username, "password": "bad"})
        assert res.status_code == 401

    # 5th failure -> triggers 429 lockout
    res5 = client.post("/api/auth/login", json={"username": username, "password": "bad"})
    assert res5.status_code == 429
    assert "locked for 1 minute" in res5.json()["detail"]

    # Even right password is now blocked during lockout
    res_locked = client.post("/api/auth/login", json={"username": username, "password": "RealPass123"})
    assert res_locked.status_code == 429


def test_get_me_authenticated_and_unauthenticated(client):
    # Unauthenticated
    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code == 401

    # Authenticate
    login_res = client.post("/api/auth/login", json={"username": "test_doctor", "password": "DoctorPass123"})
    assert login_res.status_code == 200

    # Authenticated get me
    auth_res = client.get("/api/auth/me")
    assert auth_res.status_code == 200
    assert auth_res.json()["username"] == "test_doctor"


def test_logout_clears_cookie(client):
    # Login first
    client.post("/api/auth/login", json={"username": "test_doctor", "password": "DoctorPass123"})
    assert "access_token" in client.cookies

    # Logout
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # Cookie removed / cleared
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 401

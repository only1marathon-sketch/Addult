import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
Path("data/test.db").unlink(missing_ok=True)

from unittest.mock import AsyncMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.safety import check_text  # noqa: E402

client = TestClient(app)


def register(email="adult@example.com", dob="1995-04-02"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "password123", "date_of_birth": dob, "accept_terms": True})
    return r


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_underage_signup_rejected():
    assert register("kid@example.com", "2012-01-01").status_code == 403


def test_filter_blocks_minor_and_real_people():
    assert not check_text("a 16 year old").allowed
    assert not check_text("teen at the beach").allowed
    assert not check_text("deepfake of an actress").allowed
    assert not check_text("she is unconscious").allowed
    assert check_text("two adults in a candlelit room").allowed


def test_must_verify_age_before_generating():
    token = register().json()["token"]
    r = client.post("/api/chat", headers=auth(token), json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 403


def test_full_flow_and_auto_suspend():
    token = client.post("/api/auth/login", json={"email": "adult@example.com", "password": "password123"}).json()["token"]
    assert client.post("/api/age-verification/start", headers=auth(token)).json()["age_verified"]

    with patch("app.main.chat_completion", AsyncMock(return_value="Hello there.")):
        r = client.post("/api/chat", headers=auth(token), json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200 and r.json()["reply"] == "Hello there."

    with patch("app.main.generate_image", AsyncMock(return_value=b"\x89PNG fake")):
        r = client.post("/api/generate/image", headers=auth(token), json={"prompt": "portrait of an adult woman"})
    assert r.status_code == 200

    for _ in range(3):
        r = client.post("/api/generate/image", headers=auth(token), json={"prompt": "a 15 yo"})
        assert r.status_code in (400, 403)
    assert client.get("/api/me", headers=auth(token)).status_code == 403  # suspended

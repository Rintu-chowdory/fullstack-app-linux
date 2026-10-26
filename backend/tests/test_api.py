from conftest import ADMIN_TEST_PASSWORD, admin_headers, client, register_student

"""End-to-end API tests (SQLite)."""


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz():
    r = client.get("/readyz")
    assert r.status_code == 200


def test_admin_login_ok():
    r = client.post("/api/login", json={"username": "admin", "password": ADMIN_TEST_PASSWORD})
    assert r.status_code == 200
    assert "token" in r.json()


def test_admin_login_bad_credentials():
    r = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_admin_endpoints_require_auth():
    assert client.get("/api/students").status_code == 401
    assert client.get("/api/student/me").status_code == 401


def test_student_register_and_login_and_me():
    payload = register_student()
    r = client.post("/api/students/register", data=payload["data"], files=payload["files"])
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    r = client.post("/api/student/login", json={"email": payload["data"]["email"],
                                               "password": payload["data"]["password"]})
    assert r.status_code == 200
    token = r.json()["token"]

    r = client.get("/api/student/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == sid
    assert body["email"] == payload["data"]["email"]
    assert body["photo_url"] == f"/uploads/students/{sid}.jpg"


def test_register_duplicate_email_fails():
    payload = register_student(email="dup@example.com")
    r = client.post("/api/students/register", data=payload["data"], files=payload["files"])
    assert r.status_code == 200
    r = client.post("/api/students/register", data=payload["data"], files=payload["files"])
    assert r.status_code == 400
    assert "already registered" in r.json()["detail"]


def test_register_short_password_fails():
    payload = register_student()
    payload["data"]["password"] = "short"
    r = client.post("/api/students/register", data=payload["data"], files=payload["files"])
    assert r.status_code == 400


def test_register_bad_photo_fails():
    payload = register_student()
    files = {"photo": ("photo.png", b"not-an-image", "image/png")}
    r = client.post("/api/students/register", data=payload["data"], files=files)
    assert r.status_code == 400


def test_student_token_cannot_use_admin_api():
    payload = register_student()
    r = client.post("/api/students/register", data=payload["data"], files=payload["files"])
    assert r.status_code == 200
    r = client.post("/api/student/login", json={"email": payload["data"]["email"],
                                               "password": payload["data"]["password"]})
    token = r.json()["token"]
    r = client.get("/api/students", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_admin_submission_and_list():
    headers = admin_headers()
    r = client.post(
        "/api/students",
        json={"name": "Manual Entry", "institute": "DIPTI", "batch": "B2",
              "course_name": "Linux", "module": "M2", "email": "manual@example.com"},
        headers=headers,
    )
    assert r.status_code == 200

    payload = register_student()
    assert client.post("/api/students/register", data=payload["data"],
                       files=payload["files"]).status_code == 200

    r = client.get("/api/students", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert any(s["email"] == payload["data"]["email"] for s in body["students"])

    r = client.get("/api/students", params={"search": payload["data"]["name"][:6]},
                   headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_login_rate_limit():
    for _ in range(12):
        client.post("/api/login", json={"username": "admin", "password": "wrong"})
    r = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 429

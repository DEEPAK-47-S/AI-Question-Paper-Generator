def test_teacher_login_and_role(client, teacher_headers):
    response = client.get("/api/auth/me", headers=teacher_headers)
    assert response.status_code == 200
    assert response.json()["role"] == "teacher"


def test_authentication_required(client):
    response = client.get("/api/documents")
    assert response.status_code == 401


def test_admin_can_create_and_deactivate_teacher(client, admin_headers):
    departments = client.get("/api/departments", headers=admin_headers).json()
    payload = {
        "full_name": "Prof. Test Staff", "employee_id": "TEST-100", "email": "test.staff@niet.edu",
        "department_id": departments[0]["id"], "designation": "Assistant Professor", "username": "teststaff",
        "temporary_password": "Temporary@123", "subject_ids": [], "is_active": True,
    }
    created = client.post("/api/admin/teachers", json=payload, headers=admin_headers)
    assert created.status_code == 201, created.text
    teacher_id = created.json()["id"]
    removed = client.delete(f"/api/admin/teachers/{teacher_id}", headers=admin_headers)
    assert removed.status_code == 200
    assert any(row["id"] == teacher_id and not row["is_active"] for row in client.get("/api/admin/teachers", headers=admin_headers).json())


def test_teacher_cannot_open_admin_dashboard(client, teacher_headers):
    assert client.get("/api/admin/dashboard", headers=teacher_headers).status_code == 403

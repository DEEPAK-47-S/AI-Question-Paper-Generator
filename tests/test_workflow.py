import io


def _subject(client, headers):
    return client.get("/api/subjects", headers=headers).json()[0]


def test_upload_extract_blueprint_generate_and_export(client, teacher_headers):
    subject = _subject(client, teacher_headers)
    syllabus = b"""NIET C PROGRAMMING
UNIT I - BASICS OF C PROGRAMMING
1. Variables and constants
2. Data types and operators
3. Formatted input and output
"""
    uploaded = client.post(
        "/api/documents/upload", headers=teacher_headers,
        data={"subject_id": subject["id"], "category": "syllabus"},
        files=[("files", ("syllabus.txt", io.BytesIO(syllabus), "text/plain"))],
    )
    assert uploaded.status_code == 202, uploaded.text
    document = uploaded.json()["documents"][0]
    status = client.get(f"/api/documents/{document['id']}/status", headers=teacher_headers)
    assert status.status_code == 200
    assert status.json()["analysis_status"] == "completed", status.text

    topics = client.get(f"/api/documents/subject/{subject['id']}/topics", headers=teacher_headers).json()
    assert topics["units"]
    topic = topics["units"][0]["topics"][0]["topic"]
    payload = {
        "subject_id": subject["id"], "exam_type": "Unit Test", "duration_minutes": 60,
        "total_marks": 2, "academic_year": "2026-2027", "sections": [
            {"name": "PART A", "count": 1, "marks": 2, "question_type": "Short Answer", "instructions": "Answer ALL questions", "has_choice": False}
        ],
        "selected_topics": [{"unit": "UNIT I", "topic": topic, "selected": True}],
        "difficulty": {"easy": 100, "medium": 0, "hard": 0},
    }
    blueprint = client.post("/api/question-paper/blueprint", json=payload, headers=teacher_headers)
    assert blueprint.status_code == 201, blueprint.text
    started = client.post("/api/question-paper/generate", json={"blueprint_id": blueprint.json()["id"], "title": "Test Paper"}, headers=teacher_headers)
    assert started.status_code == 202, started.text
    operation = client.get(f"/api/question-paper/operations/{started.json()['operation_id']}", headers=teacher_headers)
    assert operation.status_code == 200
    assert operation.json()["progress"] == 100, operation.text
    assert operation.json()["status"] == "completed", operation.text
    paper_id = operation.json()["paper_id"]
    paper = client.get(f"/api/question-papers/{paper_id}", headers=teacher_headers)
    assert paper.status_code == 200
    assert len(paper.json()["questions"]) == 1
    assert paper.json()["questions"][0]["sources"][0]["document_id"] == document["id"]

    pdf = client.get(f"/api/question-papers/{paper_id}/export/pdf", headers=teacher_headers)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    docx = client.get(f"/api/question-papers/{paper_id}/export/docx", headers=teacher_headers)
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")


def test_private_document_ownership(client, admin_headers, teacher_headers):
    docs = client.get("/api/documents", headers=teacher_headers).json()
    assert docs
    # Admin oversight is authorized; a different teacher receives a non-enumerating 404.
    assert client.get(f"/api/documents/{docs[0]['id']}", headers=admin_headers).status_code == 200
    subject = client.get("/api/subjects", headers=teacher_headers).json()[0]
    department = client.get("/api/departments", headers=admin_headers).json()[0]
    payload = {
        "full_name": "Second Teacher", "employee_id": "TEST-200", "email": "second@niet.edu",
        "department_id": department["id"], "designation": "Assistant Professor", "username": "secondteacher",
        "temporary_password": "Temporary@456", "subject_ids": [subject["id"]], "is_active": True,
    }
    created = client.post("/api/admin/teachers", json=payload, headers=admin_headers)
    assert created.status_code == 201, created.text
    login = client.post("/api/auth/login", json={"username": "second@niet.edu", "password": "Temporary@456"})
    second_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/documents/{docs[0]['id']}", headers=second_headers).status_code == 404

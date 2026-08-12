"""Idempotent development/bootstrap data. No generated papers or fake analytics are seeded."""
from sqlalchemy.orm import Session

from .auth.security import hash_password
from .config import get_settings
from .models import AdminProfile, Department, Regulation, Semester, Subject, TeacherProfile, User


def seed_database(db: Session) -> None:
    settings = get_settings()
    departments_data = [
        ("CSE", "Department of Computer Science and Engineering"),
        ("AI&DS", "Department of Artificial Intelligence and Data Science"),
        ("ECE", "Department of Electronics and Communication Engineering"),
        ("EEE", "Department of Electrical and Electronics Engineering"),
        ("MECH", "Department of Mechanical Engineering"),
        ("CIVIL", "Department of Civil Engineering"),
        ("AERO", "Department of Aeronautical Engineering"),
        ("IT", "Department of Information Technology"),
    ]
    for code, name in departments_data:
        if not db.query(Department).filter_by(code=code).first():
            db.add(Department(code=code, name=name))
    for ordinal in range(1, 9):
        name = f"Semester {ordinal}"
        if not db.query(Semester).filter_by(ordinal=ordinal).first():
            db.add(Semester(name=name, ordinal=ordinal))
    if not db.query(Regulation).filter_by(year=2025).first():
        db.add(Regulation(name="Regulation 2025", year=2025))
    db.commit()

    cse = db.query(Department).filter_by(code="CSE").one()
    sem3 = db.query(Semester).filter_by(ordinal=3).one()
    regulation = db.query(Regulation).filter_by(year=2025).one()
    subjects_data = [
        ("CS2501", "C Programming", 4),
        ("CS2502", "Python Programming", 4),
        ("CS2503", "Data Structures", 4),
        ("MA2501", "Engineering Mathematics", 4),
    ]
    subjects: list[Subject] = []
    for code, name, credits in subjects_data:
        item = db.query(Subject).filter_by(code=code, regulation_id=regulation.id).first()
        if not item:
            item = Subject(code=code, name=name, department_id=cse.id, semester_id=sem3.id, regulation_id=regulation.id, credits=credits)
            db.add(item)
        subjects.append(item)
    db.commit()

    admin = db.query(User).filter_by(email=settings.bootstrap_admin_email.lower()).first()
    if not admin:
        admin = User(
            email=settings.bootstrap_admin_email.lower(), username="admin", full_name="NIET Administrator",
            password_hash=hash_password(settings.bootstrap_admin_password), role="admin", designation="Academic Administrator",
            department_id=cse.id,
        )
        db.add(admin); db.flush(); db.add(AdminProfile(user_id=admin.id)); db.commit()
    teacher = db.query(User).filter_by(email=settings.bootstrap_teacher_email.lower()).first()
    if not teacher:
        teacher = User(
            email=settings.bootstrap_teacher_email.lower(), username="teacher", full_name="Dr. Ananya Kumar",
            employee_id="NIET-T001", password_hash=hash_password(settings.bootstrap_teacher_password), role="teacher",
            designation="Assistant Professor", department_id=cse.id, subjects=subjects,
        )
        db.add(teacher); db.flush(); db.add(TeacherProfile(user_id=teacher.id)); db.commit()

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth.dependencies import require_roles
from ..auth.security import hash_password
from ..database import get_db
from ..models import (
    AuditLog, Department, GeneratedQuestionPaper, GenerationLog, Subject, SystemSetting, TeacherProfile, UploadedDocument, User,
)
from ..schemas import PasswordReset, TeacherCreate, TeacherOut, TeacherUpdate
from ..services.audit import record_audit

router = APIRouter(prefix="/api/admin", tags=["Admin"])
admin_only = require_roles("admin", "super_admin")


@router.get("/dashboard")
def dashboard(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    month_ago = datetime.now(timezone.utc) - timedelta(days=30)
    cards = {
        "teachers": db.query(User).filter(User.role == "teacher", User.is_active.is_(True)).count(),
        "departments": db.query(Department).filter(Department.is_active.is_(True)).count(),
        "subjects": db.query(Subject).filter(Subject.is_active.is_(True)).count(),
        "documents": db.query(UploadedDocument).count(),
        "generated_papers": db.query(GeneratedQuestionPaper).count(),
        "papers_this_month": db.query(GeneratedQuestionPaper).filter(GeneratedQuestionPaper.created_at >= month_ago).count(),
        "pending_approvals": db.query(GeneratedQuestionPaper).filter(GeneratedQuestionPaper.status == "admin_review").count(),
    }
    recent_papers = db.query(GeneratedQuestionPaper).order_by(GeneratedQuestionPaper.created_at.desc()).limit(6).all()
    recent_teachers = db.query(User).filter(User.role == "teacher").order_by(User.created_at.desc()).limit(6).all()
    popular = (
        db.query(Subject.name, func.count(GeneratedQuestionPaper.id).label("count"))
        .outerjoin(GeneratedQuestionPaper, GeneratedQuestionPaper.subject_id == Subject.id)
        .group_by(Subject.id).order_by(func.count(GeneratedQuestionPaper.id).desc()).limit(5).all()
    )
    return {
        "cards": cards,
        "recent_papers": [{"id": p.id, "code": p.paper_code, "title": p.title, "status": p.status, "created_at": p.created_at} for p in recent_papers],
        "recent_teachers": [{"id": t.id, "name": t.full_name, "employee_id": t.employee_id, "is_active": t.is_active} for t in recent_teachers],
        "most_used_subjects": [{"name": name, "count": count} for name, count in popular],
    }


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(
    search: str | None = Query(default=None, max_length=100),
    department_id: str | None = None,
    user: User = Depends(admin_only), db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.role == "teacher")
    if search:
        term = f"%{search}%"
        query = query.filter(or_(User.full_name.ilike(term), User.email.ilike(term), User.employee_id.ilike(term)))
    if department_id:
        query = query.filter(User.department_id == department_id)
    return query.order_by(User.full_name).all()


@router.post("/teachers", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if not db.get(Department, payload.department_id):
        raise HTTPException(status_code=400, detail="Department not found")
    subjects = db.query(Subject).filter(Subject.id.in_(payload.subject_ids)).all() if payload.subject_ids else []
    if len(subjects) != len(set(payload.subject_ids)):
        raise HTTPException(status_code=400, detail="One or more assigned subjects were not found")
    teacher = User(
        full_name=payload.full_name.strip(), employee_id=payload.employee_id.strip(),
        email=payload.email.lower(), phone=payload.phone, department_id=payload.department_id,
        designation=payload.designation, username=payload.username.lower().strip(),
        password_hash=hash_password(payload.temporary_password), role="teacher",
        is_active=payload.is_active, must_change_password=True, subjects=subjects,
    )
    db.add(teacher)
    try:
        db.flush()
        db.add(TeacherProfile(user_id=teacher.id))
        record_audit(db, admin, "admin.teacher_created", "user", teacher.id, {"employee_id": teacher.employee_id})
        db.commit()
        db.refresh(teacher)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email, username, or employee ID already exists") from exc
    return teacher


@router.put("/teachers/{teacher_id}", response_model=TeacherOut)
def update_teacher(teacher_id: str, payload: TeacherUpdate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    teacher = db.get(User, teacher_id)
    if not teacher or teacher.role != "teacher":
        raise HTTPException(status_code=404, detail="Teacher not found")
    changes = payload.model_dump(exclude_unset=True)
    subject_ids = changes.pop("subject_ids", None)
    for key, value in changes.items():
        if key == "email" and value:
            value = value.lower()
        setattr(teacher, key, value)
    if subject_ids is not None:
        subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
        if len(subjects) != len(set(subject_ids)):
            raise HTTPException(status_code=400, detail="One or more subjects were not found")
        teacher.subjects = subjects
    record_audit(db, admin, "admin.teacher_updated", "user", teacher.id, {"fields": list(changes)})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Updated email conflicts with another account") from exc
    return teacher


@router.delete("/teachers/{teacher_id}")
def deactivate_teacher(teacher_id: str, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    teacher = db.get(User, teacher_id)
    if not teacher or teacher.role != "teacher":
        raise HTTPException(status_code=404, detail="Teacher not found")
    teacher.is_active = False
    teacher.auth_version += 1
    record_audit(db, admin, "admin.teacher_deactivated", "user", teacher.id)
    db.commit()
    return {"message": "Teacher deactivated; private academic records were retained for audit."}


@router.post("/teachers/{teacher_id}/reset-password")
def reset_password(teacher_id: str, payload: PasswordReset, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    teacher = db.get(User, teacher_id)
    if not teacher or teacher.role != "teacher":
        raise HTTPException(status_code=404, detail="Teacher not found")
    teacher.password_hash = hash_password(payload.temporary_password)
    teacher.must_change_password = True
    teacher.auth_version += 1
    record_audit(db, admin, "admin.teacher_password_reset", "user", teacher.id)
    db.commit()
    return {"message": "Temporary password set. The teacher must change it after sign-in."}


@router.get("/teachers/{teacher_id}/activity")
def teacher_activity(teacher_id: str, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    teacher = db.get(User, teacher_id)
    if not teacher or teacher.role != "teacher":
        raise HTTPException(status_code=404, detail="Teacher not found")
    logs = db.query(AuditLog).filter(AuditLog.actor_id == teacher_id).order_by(AuditLog.created_at.desc()).limit(100).all()
    return [{"action": log.action, "resource_type": log.resource_type, "resource_id": log.resource_id, "created_at": log.created_at} for log in logs]


@router.get("/activity-logs")
def activity_logs(admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(250).all()
    return [{"id": log.id, "actor_id": log.actor_id, "action": log.action, "resource_type": log.resource_type, "resource_id": log.resource_id, "detail": log.detail_json, "created_at": log.created_at} for log in logs]


@router.get("/generation-history")
def generation_history(admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    logs = db.query(GenerationLog).order_by(GenerationLog.created_at.desc()).limit(300).all()
    return [{
        "operation_id": log.operation_id, "owner_id": log.owner_id, "paper_id": log.paper_id,
        "stage": log.stage, "status": log.status, "progress": log.progress,
        "detail": log.detail, "created_at": log.created_at,
    } for log in logs]


@router.get("/settings")
def system_settings(admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    values = {item.key: item.value_json for item in db.query(SystemSetting).all() if not item.is_secret}
    return {
        "approval_workflow": values.get("approval_workflow", {"enabled": True}),
        "retention": values.get("retention", {"archive_days": 365}),
        "security": {"private_documents": True, "ownership_enforced": True, "audit_logging": True},
    }


@router.put("/settings/{key}")
def update_system_setting(key: str, value: dict = Body(...), admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if key not in {"approval_workflow", "retention"}:
        raise HTTPException(status_code=422, detail="This setting is not editable through the API")
    item = db.get(SystemSetting, key)
    if not item:
        item = SystemSetting(key=key)
        db.add(item)
    item.value_json = value
    item.updated_by_id = admin.id
    record_audit(db, admin, "admin.setting_updated", "system_setting", key, {"fields": list(value)})
    db.commit()
    return {"key": key, "value": value}

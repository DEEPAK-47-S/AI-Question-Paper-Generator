from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth.dependencies import get_current_user, require_roles
from ..database import get_db
from ..models import Department, Regulation, Semester, Subject, User
from ..schemas import (
    DepartmentCreate, DepartmentOut, RegulationCreate, SemesterCreate, SubjectCreate, SubjectOut,
)
from ..services.audit import record_audit

router = APIRouter(prefix="/api", tags=["Academic master data"])
admin_only = require_roles("admin", "super_admin")


@router.get("/departments", response_model=list[DepartmentOut])
def departments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Department).filter(Department.is_active.is_(True)).order_by(Department.name).all()


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = Department(code=payload.code.upper().strip(), name=payload.name.strip())
    db.add(item)
    try:
        db.flush()
        record_audit(db, admin, "academic.department_created", "department", item.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department code or name already exists") from exc
    return item


@router.put("/departments/{item_id}", response_model=DepartmentOut)
def update_department(item_id: str, payload: DepartmentCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = db.get(Department, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Department not found")
    item.code, item.name = payload.code.upper().strip(), payload.name.strip()
    record_audit(db, admin, "academic.department_updated", "department", item.id)
    db.commit()
    return item


@router.delete("/departments/{item_id}")
def remove_department(item_id: str, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = db.get(Department, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Department not found")
    item.is_active = False
    record_audit(db, admin, "academic.department_deactivated", "department", item.id)
    db.commit()
    return {"message": "Department deactivated"}


@router.get("/semesters")
def semesters(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Semester).filter(Semester.is_active.is_(True)).order_by(Semester.ordinal).all()
    return [{"id": row.id, "name": row.name, "ordinal": row.ordinal, "is_active": row.is_active} for row in rows]


@router.post("/semesters", status_code=201)
def create_semester(payload: SemesterCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = Semester(**payload.model_dump())
    db.add(item)
    try:
        db.flush(); record_audit(db, admin, "academic.semester_created", "semester", item.id); db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Semester already exists") from exc
    return {"id": item.id, "name": item.name, "ordinal": item.ordinal}


@router.get("/regulations")
def regulations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Regulation).filter(Regulation.is_active.is_(True)).order_by(Regulation.year.desc()).all()
    return [{"id": row.id, "name": row.name, "year": row.year, "is_active": row.is_active} for row in rows]


@router.post("/regulations", status_code=201)
def create_regulation(payload: RegulationCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = Regulation(**payload.model_dump())
    db.add(item)
    try:
        db.flush(); record_audit(db, admin, "academic.regulation_created", "regulation", item.id); db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Regulation already exists") from exc
    return {"id": item.id, "name": item.name, "year": item.year}


@router.get("/subjects", response_model=list[SubjectOut])
def subjects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Subject).filter(Subject.is_active.is_(True))
    if user.role == "teacher":
        query = query.join(Subject.teachers).filter(User.id == user.id)
    return query.order_by(Subject.code).all()


@router.get("/subjects/{subject_id}")
def subject_detail(subject_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Subject, subject_id)
    if not item or (user.role == "teacher" and item not in user.subjects):
        raise HTTPException(status_code=404, detail="Subject not found")
    return {
        "id": item.id, "code": item.code, "name": item.name, "credits": item.credits,
        "department": {"id": item.department.id, "name": item.department.name},
        "semester": {"id": item.semester.id, "name": item.semester.name},
        "regulation": {"id": item.regulation.id, "name": item.regulation.name},
        "units_json": item.units_json,
    }


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(payload: SubjectCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    for model, value, label in ((Department, payload.department_id, "Department"), (Semester, payload.semester_id, "Semester"), (Regulation, payload.regulation_id, "Regulation")):
        if not db.get(model, value):
            raise HTTPException(status_code=400, detail=f"{label} not found")
    item = Subject(**payload.model_dump())
    item.code = item.code.upper().strip()
    item.name = item.name.strip()
    db.add(item)
    try:
        db.flush(); record_audit(db, admin, "academic.subject_created", "subject", item.id); db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Subject code already exists for this regulation") from exc
    return item


@router.put("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: str, payload: SubjectCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = db.get(Subject, subject_id)
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    item.code = item.code.upper().strip()
    record_audit(db, admin, "academic.subject_updated", "subject", item.id)
    db.commit()
    return item


@router.delete("/subjects/{subject_id}")
def remove_subject(subject_id: str, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    item = db.get(Subject, subject_id)
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")
    item.is_active = False
    record_audit(db, admin, "academic.subject_deactivated", "subject", item.id)
    db.commit()
    return {"message": "Subject deactivated"}

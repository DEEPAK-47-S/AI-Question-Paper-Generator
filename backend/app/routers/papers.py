from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth.dependencies import enforce_owner, get_current_user
from ..database import SessionLocal, get_db
from ..exporters.paper_export import export_docx, export_pdf, export_txt
from ..models import (
    GeneratedQuestionPaper, GenerationLog, PortionTopic, Question, QuestionBank, QuestionBlueprint, QuestionPattern, QuestionSource, Subject, SystemSetting, UploadedDocument, User,
)
from ..schemas import (
    ApprovalRequest, BlueprintOut, GenerateRequest, ManualQuestionCreate, PaperBlueprintRequest,
    QuestionBankCreate, QuestionUpdate,
)
from ..services.audit import record_audit
from ..services.blueprint import build_blueprint
from ..services.generation import generate_paper, regenerate_question
from ..validators.questions import duplicate_risk

router = APIRouter(prefix="/api", tags=["Question papers"])


def _subject_access(db: Session, user: User, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if not subject or (user.role == "teacher" and subject not in user.subjects):
        raise HTTPException(status_code=404, detail="Assigned subject not found")
    return subject


def _paper_access(db: Session, user: User, paper_id: str) -> GeneratedQuestionPaper:
    paper = db.get(GeneratedQuestionPaper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found")
    enforce_owner(user, paper.owner_id)
    return paper


def _question_access(db: Session, user: User, question_id: str) -> Question:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    enforce_owner(user, question.paper.owner_id)
    return question


def _paper_json(paper: GeneratedQuestionPaper, sources: bool = True) -> dict:
    questions = []
    for q in sorted(paper.questions, key=lambda item: item.position):
        item = {
            "id": q.id, "section": q.section, "position": q.position, "question_number": q.question_number,
            "text": q.text, "alternative_text": q.alternative_text, "unit": q.unit, "topic": q.topic,
            "subtopic": q.subtopic, "difficulty": q.difficulty, "bloom_level": q.bloom_level,
            "marks": q.marks, "question_type": q.question_type, "confidence_score": q.confidence_score,
            "validation": q.validation_json, "is_manual": q.is_manual,
        }
        if sources:
            item["sources"] = [{
                "document_id": source.document_id, "document_name": source.document.original_name,
                "location": source.location, "excerpt": source.excerpt, "relevance_score": source.relevance_score,
            } for source in q.sources]
        questions.append(item)
    return {
        "id": paper.id, "paper_code": paper.paper_code, "title": paper.title, "owner_id": paper.owner_id,
        "subject": {
            "id": paper.subject.id, "name": paper.subject.name, "code": paper.subject.code,
            "department": paper.subject.department.name, "semester": paper.subject.semester.name,
            "regulation": paper.subject.regulation.name,
        },
        "exam_type": paper.exam_type, "exam_date": paper.exam_date, "duration_minutes": paper.duration_minutes,
        "total_marks": paper.total_marks, "academic_year": paper.academic_year,
        "class_section": paper.class_section, "version": paper.version, "status": paper.status,
        "settings": paper.settings_json, "coverage": paper.coverage_json,
        "approval_comment": paper.approval_comment, "created_at": paper.created_at, "updated_at": paper.updated_at,
        "questions": questions,
    }


@router.get("/teacher/dashboard")
def teacher_dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher dashboard is available to staff accounts")
    papers = db.query(GeneratedQuestionPaper).filter(GeneratedQuestionPaper.owner_id == user.id)
    documents = db.query(UploadedDocument).filter(UploadedDocument.owner_id == user.id)
    recent = papers.order_by(GeneratedQuestionPaper.updated_at.desc()).limit(6).all()
    return {
        "welcome": user.full_name,
        "cards": {
            "assigned_subjects": len(user.subjects), "uploaded_materials": documents.count(),
            "generated_papers": papers.count(), "draft_papers": papers.filter(GeneratedQuestionPaper.status == "draft").count(),
        },
        "subjects": [{"id": s.id, "code": s.code, "name": s.name, "semester": s.semester.name} for s in user.subjects],
        "recent_papers": [{"id": p.id, "code": p.paper_code, "title": p.title, "subject": p.subject.name, "status": p.status, "updated_at": p.updated_at} for p in recent],
    }


@router.post("/question-paper/blueprint", response_model=BlueprintOut, status_code=201)
def create_blueprint(payload: PaperBlueprintRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _subject_access(db, user, payload.subject_id)
    analyzed = db.query(UploadedDocument).filter(
        UploadedDocument.owner_id == user.id, UploadedDocument.subject_id == payload.subject_id,
        UploadedDocument.category == "syllabus", UploadedDocument.analysis_status == "completed",
    ).count()
    if not analyzed:
        raise HTTPException(status_code=422, detail="Upload and successfully analyze a syllabus before building a blueprint")
    allocation = build_blueprint(payload)
    db.query(PortionTopic).filter(PortionTopic.owner_id == user.id, PortionTopic.subject_id == payload.subject_id).delete()
    for topic in payload.selected_topics:
        db.add(PortionTopic(
            owner_id=user.id, subject_id=payload.subject_id, unit=topic.unit,
            topic=topic.topic, subtopic=topic.subtopic, is_selected=topic.selected,
        ))
    db.add(QuestionPattern(
        owner_id=user.id, subject_id=payload.subject_id,
        name=f"{payload.exam_type} pattern", total_marks=payload.total_marks,
        sections_json=[section.model_dump() for section in payload.sections], is_template=False,
    ))
    blueprint = QuestionBlueprint(
        owner_id=user.id, subject_id=payload.subject_id,
        request_json=payload.model_dump(mode="json"), allocation_json=allocation, total_marks=payload.total_marks,
    )
    db.add(blueprint); db.flush()
    record_audit(db, user, "paper.blueprint_created", "blueprint", blueprint.id, {"questions": allocation["total_questions"], "marks": payload.total_marks})
    db.commit()
    return blueprint


def _generation_task(blueprint_id: str, owner_id: str, title: str, operation_id: str):
    db = SessionLocal()
    try:
        generate_paper(db, blueprint_id, owner_id, title, operation_id)
    except Exception:
        # Failure is persisted as an operation log by the generation service.
        pass
    finally:
        db.close()


@router.post("/question-paper/generate", status_code=status.HTTP_202_ACCEPTED)
def start_generation(payload: GenerateRequest, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    blueprint = db.get(QuestionBlueprint, payload.blueprint_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    enforce_owner(user, blueprint.owner_id)
    operation_id = str(uuid.uuid4())
    db.add(GenerationLog(owner_id=user.id, operation_id=operation_id, stage="Generation queued", status="queued", progress=0))
    record_audit(db, user, "paper.generation_started", "blueprint", blueprint.id, {"operation_id": operation_id})
    db.commit()
    background.add_task(_generation_task, blueprint.id, user.id, payload.title, operation_id)
    return {"operation_id": operation_id, "status": "queued", "message": "Grounded generation queued"}


@router.get("/question-paper/operations/{operation_id}")
def operation_status(operation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.query(GenerationLog).filter(GenerationLog.operation_id == operation_id).order_by(GenerationLog.created_at).all()
    if not logs:
        raise HTTPException(status_code=404, detail="Generation operation not found")
    enforce_owner(user, logs[0].owner_id)
    last = logs[-1]
    return {
        "operation_id": operation_id, "status": last.status, "stage": last.stage, "progress": last.progress,
        "detail": last.detail, "paper_id": next((log.paper_id for log in reversed(logs) if log.paper_id), None),
        "stages": [{"stage": log.stage, "status": log.status, "progress": log.progress, "created_at": log.created_at} for log in logs],
    }


@router.get("/question-papers")
def list_papers(
    status_filter: str | None = Query(default=None, alias="status"), subject_id: str | None = None,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    query = db.query(GeneratedQuestionPaper)
    if user.role == "teacher":
        query = query.filter(GeneratedQuestionPaper.owner_id == user.id)
    if status_filter:
        query = query.filter(GeneratedQuestionPaper.status == status_filter)
    if subject_id:
        query = query.filter(GeneratedQuestionPaper.subject_id == subject_id)
    papers = query.order_by(GeneratedQuestionPaper.updated_at.desc()).all()
    return [{
        "id": p.id, "paper_code": p.paper_code, "title": p.title, "subject": p.subject.name,
        "department": p.subject.department.name, "semester": p.subject.semester.name,
        "regulation": p.subject.regulation.name, "exam_type": p.exam_type, "total_marks": p.total_marks,
        "version": p.version, "status": p.status, "teacher": p.owner.full_name, "created_at": p.created_at,
    } for p in papers]


@router.get("/question-papers/{paper_id}")
def paper_detail(paper_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _paper_json(_paper_access(db, user, paper_id))


@router.post("/question-papers/{paper_id}/duplicate", status_code=201)
def duplicate_paper(paper_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    original = _paper_access(db, user, paper_id)
    clone = GeneratedQuestionPaper(
        paper_code=f"NIET-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}", owner_id=user.id,
        subject_id=original.subject_id, blueprint_id=original.blueprint_id, title=f"{original.title} (Copy)",
        exam_type=original.exam_type, exam_date=original.exam_date, duration_minutes=original.duration_minutes,
        total_marks=original.total_marks, academic_year=original.academic_year, class_section=original.class_section,
        version=original.version + 1, status="draft", settings_json=original.settings_json, coverage_json=original.coverage_json,
    )
    db.add(clone); db.flush()
    for source in original.questions:
        copy = Question(
            paper_id=clone.id, section=source.section, position=source.position, question_number=source.question_number,
            text=source.text, alternative_text=source.alternative_text, unit=source.unit, topic=source.topic,
            subtopic=source.subtopic, difficulty=source.difficulty, bloom_level=source.bloom_level,
            marks=source.marks, question_type=source.question_type, confidence_score=source.confidence_score,
            validation_json=source.validation_json, is_manual=source.is_manual,
        )
        db.add(copy); db.flush()
        for provenance in source.sources:
            db.add(QuestionSource(question_id=copy.id, document_id=provenance.document_id, chunk_id=provenance.chunk_id, location=provenance.location, excerpt=provenance.excerpt, relevance_score=provenance.relevance_score))
    record_audit(db, user, "paper.duplicated", "paper", clone.id, {"source_paper": original.id}); db.commit()
    return _paper_json(clone)


@router.delete("/question-papers/{paper_id}")
def delete_paper(paper_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _paper_access(db, user, paper_id)
    record_audit(db, user, "paper.deleted", "paper", paper.id, {"code": paper.paper_code})
    db.delete(paper); db.commit()
    return {"message": "Question paper deleted"}


@router.put("/questions/{question_id}")
def edit_question(question_id: str, payload: QuestionUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    question = _question_access(db, user, question_id)
    changes = payload.model_dump(exclude_unset=True)
    new_position = changes.pop("position", None)
    for key, value in changes.items():
        setattr(question, key, value)
    if new_position is not None:
        ordered = sorted([item for item in question.paper.questions if item.id != question.id], key=lambda item: item.position)
        ordered.insert(min(new_position - 1, len(ordered)), question)
        for index, item in enumerate(ordered, 1):
            item.position = index
            item.question_number = str(index)
        changes["position"] = new_position
    question.is_manual = True
    question.confidence_score = min(question.confidence_score, 0.65)
    question.validation_json = {**question.validation_json, "passed": False, "manual_edit_requires_review": True}
    question.paper.status = "draft"
    record_audit(db, user, "question.edited", "question", question.id, {"fields": list(changes)})
    db.commit()
    return _paper_json(question.paper)


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    question = _question_access(db, user, question_id)
    paper = question.paper
    remaining = sorted([item for item in paper.questions if item.id != question.id], key=lambda item: item.position)
    for index, item in enumerate(remaining, 1):
        item.position = index; item.question_number = str(index)
    db.delete(question); paper.status = "draft"
    record_audit(db, user, "question.deleted", "paper", paper.id); db.commit()
    return {"message": "Question deleted"}


@router.post("/questions/{question_id}/regenerate")
def regenerate(question_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    question = _question_access(db, user, question_id)
    try:
        regenerate_question(db, question, question.paper.owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    question.paper.status = "generated"
    record_audit(db, user, "question.regenerated", "question", question.id); db.commit()
    return _paper_json(question.paper)


@router.post("/questions/{question_id}/duplicate", status_code=201)
def duplicate_question(question_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source = _question_access(db, user, question_id)
    paper = source.paper
    position = max([item.position for item in paper.questions] or [0]) + 1
    duplicate = Question(
        paper_id=paper.id, section=source.section, position=position, question_number=str(position),
        text=source.text, alternative_text=source.alternative_text, unit=source.unit, topic=source.topic,
        subtopic=source.subtopic, difficulty=source.difficulty, bloom_level=source.bloom_level,
        marks=source.marks, question_type=source.question_type, confidence_score=0,
        validation_json={"passed": False, "intentional_teacher_duplicate": True, "manual_review_requires_review": True},
        is_manual=True,
    )
    db.add(duplicate)
    paper.status = "draft"
    record_audit(db, user, "question.duplicated", "question", duplicate.id, {"source_question": source.id})
    db.commit()
    return _paper_json(paper)


@router.post("/question-papers/{paper_id}/questions", status_code=201)
def add_manual_question(paper_id: str, payload: ManualQuestionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _paper_access(db, user, paper_id)
    existing = [q.text for q in paper.questions]
    duplicate, score, _ = duplicate_risk(payload.text, existing)
    if duplicate:
        raise HTTPException(status_code=409, detail=f"This question is too similar to another current question ({score:.0%})")
    position = max([q.position for q in paper.questions] or [0]) + 1
    question = Question(
        paper_id=paper.id, section=payload.section, position=position, question_number=str(position),
        text=payload.text, unit=payload.unit, topic=payload.topic, difficulty=payload.difficulty,
        bloom_level=payload.bloom_level, marks=payload.marks, question_type=payload.question_type,
        confidence_score=0, validation_json={"passed": False, "manual_question_requires_review": True}, is_manual=True,
    )
    db.add(question); paper.status = "draft"
    record_audit(db, user, "question.manual_added", "question", question.id); db.commit()
    return _paper_json(paper)


@router.post("/question-paper/validate")
def validate_paper(paper_id: str = Body(..., embed=True), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _paper_access(db, user, paper_id)
    failures = [q.id for q in paper.questions if not q.validation_json.get("passed")]
    actual_marks = sum(q.marks for q in paper.questions)
    return {
        "passed": not failures and actual_marks == paper.total_marks,
        "question_failures": failures, "expected_marks": paper.total_marks, "actual_marks": actual_marks,
        "coverage": paper.coverage_json,
    }


@router.post("/question-papers/{paper_id}/approval")
def approval(paper_id: str, payload: ApprovalRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _paper_access(db, user, paper_id)
    action = payload.action
    if action == "submit":
        if user.role != "teacher" or paper.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Only the owning teacher can submit this paper")
        workflow = db.get(SystemSetting, "approval_workflow")
        enabled = workflow.value_json.get("enabled", True) if workflow else True
        paper.status = "admin_review" if enabled else "reviewed"
    elif action in {"approve", "reject", "request_changes"}:
        if user.role not in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="Administrator approval required")
        if action == "approve":
            invalid = [item.question_number for item in paper.questions if not item.validation_json.get("passed")]
            if invalid or sum(item.marks for item in paper.questions) != paper.total_marks:
                raise HTTPException(status_code=422, detail="The paper cannot be approved until all questions pass validation and marks match the pattern")
        paper.status = {"approve": "approved", "reject": "draft", "request_changes": "teacher_review"}[action]
        if action == "approve":
            paper.approved_by_id = user.id; paper.approved_at = datetime.now(timezone.utc)
    elif action == "archive":
        paper.status = "archived"
    paper.approval_comment = payload.comment
    record_audit(db, user, f"paper.{action}", "paper", paper.id); db.commit()
    return {"id": paper.id, "status": paper.status, "comment": paper.approval_comment}


@router.get("/question-papers/{paper_id}/answer-key")
def answer_key(paper_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _paper_access(db, user, paper_id)
    return {"paper_id": paper.id, "answers": [{"question_number": q.question_number, "question": q.text, "answer": q.answer_key.answer_text if q.answer_key else "Not generated"} for q in paper.questions]}


@router.get("/question-papers/{paper_id}/export/{format}")
def export_paper(format: str, paper_id: str, include_answers: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    paper = _paper_access(db, user, paper_id)
    exporters = {
        "pdf": (export_pdf, "application/pdf"),
        "docx": (export_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "txt": (export_txt, "text/plain; charset=utf-8"),
    }
    if format not in exporters:
        raise HTTPException(status_code=404, detail="Export format must be pdf, docx, or txt")
    exporter, media = exporters[format]
    content = exporter(paper, include_answers)
    suffix = "-with-answer-key" if include_answers else ""
    filename = f"{paper.paper_code}{suffix}.{format}"
    paper.status = "downloaded" if paper.status not in {"approved", "archived"} else paper.status
    record_audit(db, user, "paper.downloaded", "paper", paper.id, {"format": format, "answer_key": include_answers}); db.commit()
    return StreamingResponse(io.BytesIO(content), media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/question-patterns")
def list_question_patterns(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(QuestionPattern)
    if user.role == "teacher":
        query = query.filter(QuestionPattern.owner_id == user.id)
    rows = query.order_by(QuestionPattern.created_at.desc()).all()
    return [{
        "id": row.id, "name": row.name, "subject_id": row.subject_id,
        "total_marks": row.total_marks, "sections": row.sections_json,
        "is_template": row.is_template, "owner_id": row.owner_id, "created_at": row.created_at,
    } for row in rows]


@router.delete("/question-patterns/{pattern_id}")
def delete_question_pattern(pattern_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pattern = db.get(QuestionPattern, pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Question pattern not found")
    enforce_owner(user, pattern.owner_id)
    db.delete(pattern)
    record_audit(db, user, "pattern.deleted", "question_pattern", pattern.id)
    db.commit()
    return {"message": "Question pattern deleted"}


@router.get("/question-bank")
def list_question_bank(subject_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(QuestionBank)
    if user.role == "teacher":
        query = query.filter(QuestionBank.created_by_id == user.id)
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    rows = query.order_by(QuestionBank.created_at.desc()).all()
    return [{"id": q.id, "subject_id": q.subject_id, "question": q.question, "unit": q.unit, "topic": q.topic, "difficulty": q.difficulty, "bloom_level": q.bloom_level, "marks": q.marks, "usage_count": q.usage_count, "is_approved": q.is_approved} for q in rows]


@router.post("/question-bank", status_code=201)
def add_question_bank(payload: QuestionBankCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _subject_access(db, user, payload.subject_id)
    item = QuestionBank(created_by_id=user.id, **payload.model_dump())
    db.add(item); db.flush(); record_audit(db, user, "question_bank.added", "question_bank", item.id); db.commit()
    return {"id": item.id, **payload.model_dump(), "is_approved": item.is_approved}

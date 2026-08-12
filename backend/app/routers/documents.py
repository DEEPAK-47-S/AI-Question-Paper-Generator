from __future__ import annotations

import hashlib
import mimetypes
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..auth.dependencies import enforce_owner, get_current_user
from ..config import get_settings
from ..database import SessionLocal, get_db
from ..document_processing.extractors import SUPPORTED_EXTENSIONS
from ..document_processing.pipeline import process_document
from ..document_processing.url_fetcher import URLFetchError, fetch_public_document
from ..models import QuestionSource, SyllabusDocument, Subject, UploadedDocument, User
from ..schemas import DocumentOut, DocumentURLCreate
from ..services.audit import record_audit

router = APIRouter(prefix="/api/documents", tags=["Private document library"])
settings = get_settings()
VALID_CATEGORIES = {"syllabus", "portion", "previous_paper", "sample_paper", "question_bank", "notes", "reference", "assignment"}


def _subject_access(db: Session, user: User, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if not subject or (user.role == "teacher" and subject not in user.subjects):
        raise HTTPException(status_code=404, detail="Assigned subject not found")
    return subject


def _process_task(document_id: str):
    db = SessionLocal()
    try:
        document = db.get(UploadedDocument, document_id)
        if document and document.stored_name:
            process_document(db, document, settings.upload_dir / document.stored_name)
    except Exception:
        # Pipeline records a sanitized user-facing error on the document.
        pass
    finally:
        db.close()


def _serialize(document: UploadedDocument) -> dict:
    return {field: getattr(document, field) for field in (
        "id", "subject_id", "category", "original_name", "mime_type", "extension", "size_bytes",
        "processing_status", "analysis_status", "processing_stage", "error_message", "page_count",
        "metadata_json", "created_at",
    )}


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
def upload_documents(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    subject_id: str = Form(...),
    category: str = Form("reference"),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _subject_access(db, user, subject_id)
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail="Invalid document category")
    created: list[UploadedDocument] = []
    for upload in files:
        original = Path(upload.filename or "document").name
        extension = Path(original).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"Unsupported file type '{extension or 'unknown'}' for {original}")
        stored = f"{uuid.uuid4().hex}{extension}"
        path = settings.upload_dir / stored
        digest = hashlib.sha256()
        size = 0
        with path.open("wb") as destination:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_size:
                    destination.close(); path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"{original} exceeds the configured upload limit")
                digest.update(chunk)
                destination.write(chunk)
        if not size:
            path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"{original} is empty")
        document = UploadedDocument(
            owner_id=user.id, subject_id=subject_id, category=category, original_name=original,
            stored_name=stored, mime_type=upload.content_type or mimetypes.guess_type(original)[0] or "application/octet-stream",
            extension=extension, size_bytes=size, sha256=digest.hexdigest(),
        )
        db.add(document)
        db.flush()
        record_audit(db, user, "document.uploaded", "document", document.id, {"name": original, "category": category, "size": size})
        created.append(document)
    db.commit()
    for document in created:
        background.add_task(_process_task, document.id)
    return {"documents": [_serialize(document) for document in created], "message": "Upload completed; extraction has started."}


@router.post("/url", status_code=status.HTTP_202_ACCEPTED)
def add_url(payload: DocumentURLCreate, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _subject_access(db, user, payload.subject_id)
    temp_dir = settings.upload_dir / f"fetch-{uuid.uuid4().hex}"
    try:
        fetched, filename, mime_type, size = fetch_public_document(payload.url, temp_dir)
        extension = fetched.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise URLFetchError(f"The public link returned unsupported content ({mime_type}).")
        stored = f"{uuid.uuid4().hex}{extension}"
        final = settings.upload_dir / stored
        shutil.move(str(fetched), final)
    except URLFetchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    document = UploadedDocument(
        owner_id=user.id, subject_id=payload.subject_id, category=payload.category,
        original_name=filename, stored_name=stored, source_url=payload.url,
        mime_type=mime_type, extension=extension, size_bytes=size,
        sha256=hashlib.sha256(final.read_bytes()).hexdigest(),
    )
    db.add(document); db.flush()
    record_audit(db, user, "document.url_added", "document", document.id, {"host": Path(payload.url).name, "category": payload.category})
    db.commit()
    background.add_task(_process_task, document.id)
    return {"document": _serialize(document), "message": "Link accessible; content extraction has started."}


@router.get("", response_model=list[DocumentOut])
def list_documents(subject_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(UploadedDocument)
    if user.role == "teacher":
        query = query.filter(UploadedDocument.owner_id == user.id)
    if subject_id:
        query = query.filter(UploadedDocument.subject_id == subject_id)
    return query.order_by(UploadedDocument.created_at.desc()).all()


@router.get("/{document_id}")
def document_detail(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    enforce_owner(user, document.owner_id)
    data = _serialize(document)
    data["source_url"] = document.source_url
    data["chunks"] = [{"id": c.id, "index": c.chunk_index, "unit": c.unit, "topic": c.topic, "location": c.location, "preview": c.content[:300]} for c in document.chunks]
    return data


@router.get("/{document_id}/status")
def document_status(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    enforce_owner(user, document.owner_id)
    return {"id": document.id, "processing_status": document.processing_status, "analysis_status": document.analysis_status, "stage": document.processing_stage, "error": document.error_message, "metadata": document.metadata_json}


@router.get("/{document_id}/download")
def download_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    enforce_owner(user, document.owner_id)
    path = settings.upload_dir / (document.stored_name or "")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file not found")
    record_audit(db, user, "document.downloaded", "document", document.id); db.commit()
    return FileResponse(path, filename=document.original_name, media_type=document.mime_type)


@router.put("/{document_id}/structure")
def update_structure(document_id: str, units: list[dict] = Body(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    enforce_owner(user, document.owner_id)
    if document.category != "syllabus":
        raise HTTPException(status_code=400, detail="Only syllabus structure can be edited")
    if any(not item.get("unit") or not isinstance(item.get("topics", []), list) for item in units):
        raise HTTPException(status_code=422, detail="Each unit requires a unit label and topics list")
    document.metadata_json = {**document.metadata_json, "units": units, "structure_edited": True}
    syllabus = db.query(SyllabusDocument).filter_by(document_id=document.id).first()
    if syllabus:
        syllabus.structured_units = units
    record_audit(db, user, "document.structure_edited", "document", document.id)
    db.commit()
    return {"units": units}


@router.post("/{document_id}/analyze", status_code=202)
def reanalyze(document_id: str, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    enforce_owner(user, document.owner_id)
    if db.query(QuestionSource).filter(QuestionSource.document_id == document.id).count():
        raise HTTPException(status_code=409, detail="This document is cited by a generated paper and cannot be re-indexed without changing its provenance.")
    document.processing_status = "queued"; document.analysis_status = "pending"; document.processing_stage = "Queued for re-analysis"; document.error_message = None
    record_audit(db, user, "document.reanalysis_requested", "document", document.id); db.commit()
    background.add_task(_process_task, document.id)
    return {"message": "Re-analysis queued"}


@router.delete("/{document_id}")
def delete_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.get(UploadedDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    enforce_owner(user, document.owner_id)
    if db.query(QuestionSource).filter(QuestionSource.document_id == document.id).count():
        raise HTTPException(status_code=409, detail="This document is cited by a generated paper. Delete the dependent paper first to preserve its audit trail.")
    path = settings.upload_dir / (document.stored_name or "")
    record_audit(db, user, "document.deleted", "document", document.id, {"name": document.original_name})
    db.delete(document); db.commit(); path.unlink(missing_ok=True)
    return {"message": "Document and its private index were deleted"}


@router.get("/subject/{subject_id}/topics")
def subject_topics(subject_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _subject_access(db, user, subject_id)
    query = db.query(UploadedDocument).filter(
        UploadedDocument.owner_id == user.id,
        UploadedDocument.subject_id == subject_id,
        UploadedDocument.category == "syllabus",
        UploadedDocument.analysis_status == "completed",
    ).order_by(UploadedDocument.created_at.desc())
    documents = query.all()
    units: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for document in documents:
        for unit in document.metadata_json.get("units", []):
            target = next((u for u in units if u["unit"] == unit.get("unit")), None)
            if not target:
                target = {"unit": unit.get("unit"), "title": unit.get("title", ""), "topics": [], "source_document_id": document.id}
                units.append(target)
            for topic in unit.get("topics", []):
                label = topic.get("topic") if isinstance(topic, dict) else str(topic)
                key = (target["unit"], label.lower())
                if label and key not in seen:
                    target["topics"].append({"topic": label, "selected": True})
                    seen.add(key)
    return {"units": units, "documents_analyzed": len(documents)}

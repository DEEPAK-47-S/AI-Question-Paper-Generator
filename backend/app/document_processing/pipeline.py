"""Validation → extraction/OCR → cleaning → chunking → classification → indexing pipeline."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import (
    DocumentChunk, DocumentEmbedding, PreviousQuestionPaper, SyllabusDocument, UploadedDocument,
)
from .extractors import ExtractionResult, extract_document

UNIT_RE = re.compile(r"^\s*(?:UNIT|MODULE)\s*[-:]?\s*([IVXLC]+|\d+)\s*(?:[-–—:]\s*)?(.*)$", re.I)
TOPIC_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?|[a-z][.)]|[-•])\s+(.+)$", re.I)
QUESTION_RE = re.compile(r"(?:^|\n)\s*(?:Q(?:uestion)?\s*)?\d+[.)]\s+(.+?)(?=\n\s*(?:Q(?:uestion)?\s*)?\d+[.)]|$)", re.I | re.S)
MARK_RE = re.compile(r"(?:\(|\[)?\s*(\d{1,2})\s*(?:marks?|m)\s*(?:\)|\])?", re.I)


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    seen: set[str] = set()
    output: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        fingerprint = re.sub(r"\W+", "", line.lower())
        # Remove repeated headers/footers while preserving short unit/topic labels.
        if len(fingerprint) > 35 and fingerprint in seen:
            continue
        if fingerprint:
            seen.add(fingerprint)
        output.append(line)
    return "\n".join(output).strip()


def extract_structure(text: str) -> list[dict]:
    """Extract editable units/topics without inventing missing syllabus content."""
    units: list[dict] = []
    current: dict | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip(" #\t")
        if not line:
            continue
        unit_match = UNIT_RE.match(line)
        if unit_match:
            label = f"UNIT {unit_match.group(1).upper()}"
            current = {"unit": label, "title": unit_match.group(2).strip(" -–—:") or label, "topics": []}
            units.append(current)
            continue
        if current is None:
            continue
        topic_match = TOPIC_RE.match(line)
        candidate = topic_match.group(1).strip() if topic_match else line
        # Syllabus topic runs commonly use dashes/semicolons in one line.
        candidates = re.split(r"\s*[;•]\s*|\s+[-–—]\s+(?=[A-Z])", candidate)
        for item in candidates:
            item = re.sub(r"\s+", " ", item).strip(" .,:;-")
            if 2 <= len(item) <= 180 and not MARK_RE.fullmatch(item):
                if item.lower() not in {t["topic"].lower() for t in current["topics"]}:
                    current["topics"].append({"topic": item, "subtopics": [], "important_concepts": []})
    # Avoid returning an enormous paragraph as a topic.
    for unit in units:
        unit["topics"] = [topic for topic in unit["topics"] if len(topic["topic"].split()) <= 20][:80]
    return units


def _topic_for_text(text: str, structure: list[dict], unit: str | None) -> str | None:
    if not unit:
        return None
    target = next((item for item in structure if item["unit"] == unit), None)
    if not target:
        return None
    lowered = text.lower()
    matches = [topic["topic"] for topic in target["topics"] if topic["topic"].lower() in lowered]
    return min(matches, key=len) if matches else (target["topics"][0]["topic"] if target["topics"] else target["title"])


def make_chunks(result: ExtractionResult, structure: list[dict], category: str, target_chars: int = 1400) -> list[dict]:
    chunks: list[dict] = []
    current_unit: str | None = None
    for section in result.sections:
        cleaned = clean_text(section.text)
        if not cleaned:
            continue
        buffer = ""
        buffer_unit = current_unit

        def flush() -> None:
            nonlocal buffer
            if buffer.strip():
                chunks.append({"content": buffer.strip(), "location": section.location, "unit": buffer_unit})
                buffer = ""

        # Unit headings are hard chunk boundaries even when the source has no blank lines.
        # This prevents content from Unit I being retrieved for a Unit II requirement.
        for line in cleaned.splitlines():
            line = line.strip()
            if not line:
                if buffer and len(buffer) > target_chars // 2:
                    flush()
                continue
            unit_match = UNIT_RE.match(line)
            if unit_match:
                flush()
                current_unit = f"UNIT {unit_match.group(1).upper()}"
                buffer_unit = current_unit
            if buffer and len(buffer) + len(line) + 1 > target_chars:
                overlap = buffer[-180:]
                flush()
                buffer = overlap + "\n" if overlap else ""
                buffer_unit = current_unit
            buffer = f"{buffer}\n{line}".strip()
        flush()
    unique: list[dict] = []
    hashes: set[str] = set()
    for chunk in chunks:
        digest = hashlib.sha256(re.sub(r"\W+", "", chunk["content"].lower()).encode()).hexdigest()
        if digest in hashes:
            continue
        hashes.add(digest)
        chunk["hash"] = digest
        chunk["topic"] = _topic_for_text(chunk["content"], structure, chunk["unit"])
        chunk["classification"] = "question" if category in {"previous_paper", "sample_paper", "question_bank"} else category
        unique.append(chunk)
    return unique


def analyze_previous_paper(text: str) -> dict:
    questions = [re.sub(r"\s+", " ", q).strip()[:1000] for q in QUESTION_RE.findall(text)]
    marks = [int(value) for value in MARK_RE.findall(text)]
    sections = re.findall(r"(?:PART|SECTION)\s+([A-Z])", text, re.I)
    stems = re.findall(r"\b(explain|define|compare|derive|calculate|write|implement|discuss|analyze|evaluate)\b", text, re.I)
    frequency: dict[str, int] = {}
    for stem in stems:
        frequency[stem.capitalize()] = frequency.get(stem.capitalize(), 0) + 1
    return {
        "question_count": len(questions),
        "questions": questions[:200],
        "marks_detected": marks[:200],
        "sections": list(dict.fromkeys(s.upper() for s in sections)),
        "question_styles": frequency,
        "note": "Format/style reference only; questions are excluded from allowed syllabus content.",
    }


@dataclass
class PipelineOutput:
    structure: list[dict]
    chunk_count: int
    metadata: dict


def process_document(
    db: Session,
    document: UploadedDocument,
    file_path: Path,
    stage_callback: Callable[[str], None] | None = None,
) -> PipelineOutput:
    def stage(label: str):
        document.processing_stage = label
        if stage_callback:
            stage_callback(label)
        db.commit()

    try:
        document.processing_status = "processing"
        document.analysis_status = "processing"
        stage("Validating file")
        stage("Extracting document text")
        extracted = extract_document(file_path, document.extension)
        stage("Cleaning extracted content")
        cleaned_sections = type(extracted)(
            sections=[type(section)(clean_text(section.text), section.location) for section in extracted.sections],
            metadata=extracted.metadata,
        )
        full_text = cleaned_sections.text
        stage("Detecting syllabus structure")
        structure = extract_structure(full_text)
        stage("Classifying and chunking content")
        chunks = make_chunks(cleaned_sections, structure, document.category)
        if not chunks:
            raise ValueError("No indexable content was found in this document.")

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.flush()
        for index, item in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=item["content"], unit=item["unit"], topic=item["topic"],
                location=item["location"], token_estimate=max(1, len(item["content"]) // 4),
                content_hash=item["hash"], classification=item["classification"],
            )
            db.add(chunk)
            db.flush()
            # Lexical index is database-backed; vector_ref can later point to FAISS/pgvector.
            db.add(DocumentEmbedding(chunk_id=chunk.id, provider="lexical", vector_ref=None))

        document.extracted_text = full_text
        document.page_count = extracted.page_count
        document.metadata_json = {**extracted.metadata, "units": structure, "chunk_count": len(chunks)}
        if document.category == "syllabus" and document.subject_id:
            syllabus = db.query(SyllabusDocument).filter_by(document_id=document.id).first()
            if not syllabus:
                syllabus = SyllabusDocument(document_id=document.id, subject_id=document.subject_id)
                db.add(syllabus)
            syllabus.structured_units = structure
        if document.category in {"previous_paper", "sample_paper"}:
            previous = db.query(PreviousQuestionPaper).filter_by(document_id=document.id).first()
            if not previous:
                previous = PreviousQuestionPaper(document_id=document.id)
                db.add(previous)
            previous.analysis_json = analyze_previous_paper(full_text)

        document.processing_status = "completed"
        document.analysis_status = "completed"
        document.processing_stage = "AI analysis completed"
        document.error_message = None
        db.commit()
        return PipelineOutput(structure, len(chunks), document.metadata_json)
    except Exception as exc:
        document.processing_status = "failed"
        document.analysis_status = "failed"
        document.processing_stage = "Processing failed"
        document.error_message = str(exc)[:1000]
        db.commit()
        raise

"""Grounded generation, provenance mapping, regeneration and validation orchestration."""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from ..ai.providers import get_ai_provider
from ..models import (
    AnswerKey, GeneratedQuestionPaper, GenerationLog, PreviousQuestionPaper, Question, QuestionBlueprint,
    QuestionSource, UploadedDocument,
)
from ..rag.retriever import LexicalRetriever
from ..validators.questions import duplicate_risk, validate_question


class GenerationFailure(ValueError):
    pass


def _log(db: Session, owner_id: str, operation_id: str, stage: str, status: str, progress: int, paper_id: str | None = None, detail: str | None = None):
    db.add(GenerationLog(
        owner_id=owner_id, paper_id=paper_id, operation_id=operation_id,
        stage=stage, status=status, progress=progress, detail=detail,
    ))
    db.commit()


def _previous_rows(db: Session, owner_id: str, subject_id: str) -> list[PreviousQuestionPaper]:
    return (
        db.query(PreviousQuestionPaper)
        .join(UploadedDocument, UploadedDocument.id == PreviousQuestionPaper.document_id)
        .filter(UploadedDocument.owner_id == owner_id, UploadedDocument.subject_id == subject_id)
        .all()
    )


def _previous_questions(db: Session, owner_id: str, subject_id: str) -> list[str]:
    rows = _previous_rows(db, owner_id, subject_id)
    output: list[str] = []
    for row in rows:
        output.extend(row.analysis_json.get("questions", []))
    return output


def _previous_style(db: Session, owner_id: str, subject_id: str) -> str | None:
    frequency: dict[str, int] = defaultdict(int)
    for row in _previous_rows(db, owner_id, subject_id):
        for stem, count in row.analysis_json.get("question_styles", {}).items():
            frequency[stem] += count
    return max(frequency, key=frequency.get) if frequency else None


def _create_one(
    db: Session, owner_id: str, subject_id: str, spec: dict, existing: list[str], previous: list[str],
    variation_start: int = 0, style_hint: str | None = None,
):
    retriever = LexicalRetriever()
    hits = retriever.available_topic_content(db, owner_id, subject_id, spec["unit"], spec["topic"])
    if not hits:
        raise GenerationFailure(
            f"Insufficient syllabus/reference information available to generate a reliable question for {spec['unit']} — {spec['topic']}."
        )
    provider = get_ai_provider()
    allowed_topics = [{"unit": spec["unit"], "topic": spec["topic"], "selected": True}]
    result = None
    validation = None
    for attempt in range(5):
        result = provider.generate_question(
            topic=spec["topic"], unit=spec["unit"], marks=spec["marks"],
            question_type=spec["question_type"], difficulty=spec["difficulty"],
            bloom=spec["bloom_level"], hits=hits, variation=variation_start + attempt,
            style_hint=style_hint,
        )
        validation = validate_question(
            result.question, spec["unit"], spec["topic"], spec["marks"],
            allowed_topics, hits[0].chunk.content, existing + previous,
        )
        if validation["passed"]:
            second_pass = provider.validate_question(
                question=result.question, topic=spec["topic"], unit=spec["unit"],
                marks=spec["marks"], source=hits[0].chunk.content,
            )
            validation["second_ai_pass"] = second_pass
            if second_pass.get("available") and not second_pass.get("passed"):
                validation["passed"] = False
                continue
            if second_pass.get("available"):
                validation["technically_correct"] = second_pass.get("technically_correct")
            break
    if not result or not validation or not validation["passed"]:
        reason = "duplicate risk" if validation and validation.get("duplicate") else "constraint validation"
        raise GenerationFailure(f"Unable to produce a valid distinct question for {spec['topic']} after automatic regeneration ({reason}).")
    confidence = 0.86
    confidence += 0.05 if hits[0].document.category == "syllabus" else 0
    confidence += min(0.05, hits[0].score / 100)
    return result, validation, hits, round(min(confidence, 0.98), 3)


def generate_paper(db: Session, blueprint_id: str, owner_id: str, title: str, operation_id: str) -> GeneratedQuestionPaper:
    blueprint = db.get(QuestionBlueprint, blueprint_id)
    if not blueprint or blueprint.owner_id != owner_id:
        raise GenerationFailure("Blueprint not found")
    request = blueprint.request_json
    allocation = blueprint.allocation_json["allocation"]
    _log(db, owner_id, operation_id, "Retrieving selected syllabus content", "running", 15)
    previous = _previous_questions(db, owner_id, blueprint.subject_id)
    style_hint = _previous_style(db, owner_id, blueprint.subject_id)
    influence_slots = round(len(allocation) * request.get("previous_paper_influence", 20) / 100) if style_hint else 0
    style_detail = f"; format hint: {style_hint} on {influence_slots} slots" if style_hint else ""
    _log(db, owner_id, operation_id, "Comparing previous papers", "completed", 25, detail=f"Compared {len(previous)} prior questions{style_detail}")

    paper = GeneratedQuestionPaper(
        paper_code=f"NIET-{date.today().year}-{uuid.uuid4().hex[:8].upper()}",
        owner_id=owner_id, subject_id=blueprint.subject_id, blueprint_id=blueprint.id,
        title=title, exam_type=request["exam_type"],
        exam_date=date.fromisoformat(request["exam_date"]) if request.get("exam_date") else None,
        duration_minutes=request["duration_minutes"], total_marks=request["total_marks"],
        academic_year=request["academic_year"], class_section=request.get("class_section"),
        status="draft", settings_json=request,
    )
    db.add(paper)
    db.flush()
    _log(db, owner_id, operation_id, "Generating grounded questions", "running", 30, paper.id)
    current: list[str] = []
    passed = 0
    unit_question_topics: dict[str, set[str]] = defaultdict(set)
    primary_topics_by_unit: dict[str, set[str]] = defaultdict(set)
    for allocated in allocation:
        primary_topics_by_unit[allocated["unit"]].add(allocated["topic"])
    try:
        for index, spec in enumerate(allocation):
            result, validation, hits, confidence = _create_one(
                db, owner_id, blueprint.subject_id, spec, current, previous,
                style_hint=style_hint if index < influence_slots else None,
            )
            question = Question(
                paper_id=paper.id, section=spec["section"], position=index + 1,
                question_number=spec["question_number"], text=result.question,
                unit=spec["unit"], topic=spec["topic"], subtopic=spec.get("subtopic"),
                difficulty=result.difficulty, bloom_level=result.bloom_level, marks=spec["marks"],
                question_type=spec["question_type"], confidence_score=confidence,
                validation_json={**validation, "rationale": result.rationale, "provider": get_ai_provider().name},
            )
            db.add(question)
            db.flush()
            for hit in hits[:2]:
                db.add(QuestionSource(
                    question_id=question.id, document_id=hit.document.id, chunk_id=hit.chunk.id,
                    location=hit.chunk.location, excerpt=hit.chunk.content[:1000], relevance_score=hit.score,
                ))
            if result.answer_key:
                db.add(AnswerKey(question_id=question.id, answer_text=result.answer_key, evaluation_points=[]))
            if spec.get("has_choice"):
                # Either/or alternatives use another selected topic from the same unit where possible,
                # preventing a paraphrased semantic duplicate of the primary question.
                alternatives = [
                    item for item in request["selected_topics"]
                    if item.get("selected", True) and item["unit"] == spec["unit"]
                    and item["topic"] != spec["topic"]
                    and item["topic"] not in primary_topics_by_unit[spec["unit"]]
                ]
                if not alternatives:
                    raise GenerationFailure(f"An either/or choice for {spec['unit']} needs at least two selected, grounded topics.")
                alt_spec = {**spec, "topic": alternatives[index % len(alternatives)]["topic"]}
                alt_result, alt_validation, alt_hits, _ = _create_one(
                    db, owner_id, blueprint.subject_id, alt_spec, current + [result.question], previous,
                    variation_start=7, style_hint=style_hint if index < influence_slots else None,
                )
                question.alternative_text = alt_result.question
                question.validation_json = {
                    **question.validation_json, "alternative_validation": alt_validation,
                    "alternative_unit": alt_spec["unit"], "alternative_topic": alt_spec["topic"],
                }
                for hit in alt_hits[:1]:
                    db.add(QuestionSource(
                        question_id=question.id, document_id=hit.document.id, chunk_id=hit.chunk.id,
                        location=hit.chunk.location, excerpt=hit.chunk.content[:1000], relevance_score=hit.score,
                    ))
                current.append(alt_result.question)
            current.append(result.question)
            passed += 1
            unit_question_topics[spec["unit"]].add(spec["topic"])
            db.commit()
            progress = 30 + int((index + 1) / len(allocation) * 45)
            _log(db, owner_id, operation_id, f"Generated question {index + 1} of {len(allocation)}", "completed", progress, paper.id)

        _log(db, owner_id, operation_id, "Validating questions and paper pattern", "running", 82, paper.id)
        selected = [item for item in request["selected_topics"] if item.get("selected", True)]
        selected_by_unit: dict[str, set[str]] = defaultdict(set)
        for item in selected:
            selected_by_unit[item["unit"]].add(item["topic"])
        unit_coverage = {
            unit: round(100 * len(unit_question_topics.get(unit, set())) / max(1, len(topics)))
            for unit, topics in selected_by_unit.items()
        }
        question_marks = sum(question.marks for question in paper.questions)
        paper.coverage_json = {
            "syllabus_coverage": round(sum(unit_coverage.values()) / max(1, len(unit_coverage))),
            "unit_coverage": unit_coverage,
            "portion_compliance": round(100 * passed / max(1, len(allocation))),
            "pattern_compliance": 100 if question_marks == paper.total_marks else round(100 * min(question_marks, paper.total_marks) / max(question_marks, paper.total_marks)),
            "duplicate_risk": "Low",
            "out_of_syllabus_risk": "Very Low",
            "indicator_note": "AI/local validation confidence indicator, not a guarantee. Teacher review is required.",
        }
        paper.status = "generated"
        db.commit()
        _log(db, owner_id, operation_id, "Finalizing question paper", "completed", 100, paper.id)
        return paper
    except Exception as exc:
        db.rollback()
        # Remove any partial paper so invalid questions are never displayed.
        partial = db.get(GeneratedQuestionPaper, paper.id)
        if partial:
            db.delete(partial)
            db.commit()
        _log(db, owner_id, operation_id, "Generation failed", "failed", 100, detail=str(exc)[:1000])
        raise


def regenerate_question(db: Session, question: Question, owner_id: str) -> Question:
    paper = question.paper
    spec = {
        "unit": question.unit, "topic": question.topic, "marks": question.marks,
        "question_type": question.question_type, "difficulty": question.difficulty,
        "bloom_level": question.bloom_level,
    }
    existing = [item.text for item in paper.questions if item.id != question.id] + [question.text]
    previous = _previous_questions(db, owner_id, paper.subject_id)
    result, validation, hits, confidence = _create_one(db, owner_id, paper.subject_id, spec, existing, previous, variation_start=11)
    question.text = result.question
    question.confidence_score = confidence
    question.validation_json = {**validation, "rationale": result.rationale, "provider": get_ai_provider().name}
    for source in list(question.sources):
        db.delete(source)
    for hit in hits[:2]:
        db.add(QuestionSource(
            question_id=question.id, document_id=hit.document.id, chunk_id=hit.chunk.id,
            location=hit.chunk.location, excerpt=hit.chunk.content[:1000], relevance_score=hit.score,
        ))
    if question.answer_key:
        question.answer_key.answer_text = result.answer_key
    elif result.answer_key:
        db.add(AnswerKey(question_id=question.id, answer_text=result.answer_key, evaluation_points=[]))
    db.commit()
    return question

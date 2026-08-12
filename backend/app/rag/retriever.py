"""Replaceable local lexical retrieval with strict owner/subject/category boundaries."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import DocumentChunk, UploadedDocument

STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "from", "unit", "topic"}
GROUNDING_CATEGORIES = {"syllabus", "portion", "notes", "reference", "assignment", "question_bank"}


def tokens(text: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9+#]+", text.lower()) if len(word) > 1 and word not in STOPWORDS]


@dataclass
class RetrievalHit:
    chunk: DocumentChunk
    document: UploadedDocument
    score: float


class LexicalRetriever:
    """Small-deployment RAG backend. Its interface can be replaced by pgvector/FAISS."""

    def retrieve(
        self,
        db: Session,
        owner_id: str,
        subject_id: str,
        query: str,
        unit: str | None = None,
        limit: int = 5,
    ) -> list[RetrievalHit]:
        rows = (
            db.query(DocumentChunk, UploadedDocument)
            .join(UploadedDocument, UploadedDocument.id == DocumentChunk.document_id)
            .filter(
                UploadedDocument.owner_id == owner_id,
                UploadedDocument.subject_id == subject_id,
                UploadedDocument.analysis_status == "completed",
                UploadedDocument.category.in_(GROUNDING_CATEGORIES),
            )
            .all()
        )
        query_terms = set(tokens(query))
        scored: list[RetrievalHit] = []
        for chunk, document in rows:
            chunk_terms = tokens(chunk.content)
            if not chunk_terms:
                continue
            frequencies = {term: chunk_terms.count(term) for term in query_terms}
            overlap = sum(1 + math.log(count) for count in frequencies.values() if count)
            topic_exact = bool(chunk.topic and chunk.topic.lower() in query.lower())
            unit_match = not unit or (chunk.unit and chunk.unit.lower() == unit.lower())
            category_boost = 3.0 if document.category == "syllabus" else 1.5 if document.category == "portion" else 1.0
            score = overlap * category_boost + (3.0 if topic_exact else 0) + (2.0 if unit_match else -2.0)
            if score > 0 and (not unit or unit_match):
                scored.append(RetrievalHit(chunk, document, round(score, 4)))
        scored.sort(key=lambda hit: (hit.score, hit.document.category == "syllabus"), reverse=True)
        return scored[:limit]

    def available_topic_content(self, db: Session, owner_id: str, subject_id: str, unit: str, topic: str) -> list[RetrievalHit]:
        hits = self.retrieve(db, owner_id, subject_id, f"{unit} {topic}", unit, limit=8)
        topic_terms = set(tokens(topic))
        # Strict grounding: at least one meaningful topic term must occur in source text.
        return [hit for hit in hits if topic_terms.intersection(tokens(hit.chunk.content))]

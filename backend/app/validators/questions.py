"""Deterministic first-pass validation and semantic duplicate-risk detection."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..rag.retriever import tokens


def normalize_question(text: str) -> str:
    text = re.sub(r"\b(explain|describe|discuss|define|state|write a note on)\b", "", text.lower())
    return re.sub(r"\W+", " ", text).strip()


def _concept_tokens(text: str) -> set[str]:
    filler = {"perform", "performed", "using", "suitable", "briefly", "main", "concept", "principle"}
    output: set[str] = set()
    for word in tokens(text):
        if word in filler:
            continue
        # Lightweight stemming catches operations/operation without external models.
        if word.endswith("ies") and len(word) > 4:
            word = word[:-3] + "y"
        elif word.endswith("s") and not word.endswith("ss") and len(word) > 4:
            word = word[:-1]
        output.add(word)
    return output


def similarity(left: str, right: str) -> float:
    a, b = normalize_question(left), normalize_question(right)
    if not a or not b:
        return 0.0
    set_a, set_b = _concept_tokens(a), _concept_tokens(b)
    intersection = len(set_a & set_b)
    jaccard = intersection / max(1, len(set_a | set_b))
    containment = intersection / max(1, min(len(set_a), len(set_b)))
    sequence = SequenceMatcher(None, a, b).ratio()
    return max(jaccard, containment, sequence * 0.85)


def duplicate_risk(candidate: str, existing: list[str], threshold: float = 0.78) -> tuple[bool, float, str | None]:
    best_score, best_text = 0.0, None
    for text in existing:
        score = similarity(candidate, text)
        if score > best_score:
            best_score, best_text = score, text
    return best_score >= threshold, round(best_score, 3), best_text


def validate_question(
    text: str,
    unit: str,
    topic: str,
    marks: int,
    allowed_topics: list[dict],
    source_excerpt: str,
    existing: list[str],
) -> dict:
    allowed = any(
        item.get("selected", True)
        and item["unit"].strip().lower() == unit.strip().lower()
        and item["topic"].strip().lower() == topic.strip().lower()
        for item in allowed_topics
    )
    topic_grounded = bool(set(tokens(topic)) & set(tokens(source_excerpt)))
    duplicate, score, _ = duplicate_risk(text, existing)
    grammar_ok = text.strip().endswith(("?", ".")) and len(text.split()) >= 5
    marks_ok = marks > 0 and (marks <= 3 or len(text.split()) >= 6)
    passed = allowed and topic_grounded and not duplicate and grammar_ok and marks_ok
    return {
        "passed": passed,
        "inside_selected_portion": allowed,
        "source_supports_topic": topic_grounded,
        "duplicate": duplicate,
        "duplicate_similarity": score,
        "grammar": grammar_ok,
        "marks_appropriate": marks_ok,
        "technically_correct": None,
        "note": "Technical correctness is provider-validated when an external AI provider is configured; source and constraint checks always run locally.",
    }

"""Constraint-aware question-paper blueprint allocation."""
from __future__ import annotations

from collections import defaultdict

from ..schemas import PaperBlueprintRequest


def _largest_remainder(total: int, weights: dict[str, int]) -> dict[str, int]:
    if not weights:
        return {}
    weight_sum = sum(weights.values()) or 1
    exact = {key: total * value / weight_sum for key, value in weights.items()}
    allocated = {key: int(value) for key, value in exact.items()}
    remaining = total - sum(allocated.values())
    order = sorted(weights, key=lambda key: exact[key] - allocated[key], reverse=True)
    for key in order[:remaining]:
        allocated[key] += 1
    return allocated


def _label_sequence(total: int, weights: dict[str, int]) -> list[str]:
    counts = _largest_remainder(total, weights)
    sequence: list[str] = []
    # Interleave labels rather than placing all Easy questions first.
    while len(sequence) < total:
        for label in weights:
            if counts.get(label, 0) > 0:
                sequence.append(label)
                counts[label] -= 1
    return sequence


def build_blueprint(request: PaperBlueprintRequest) -> dict:
    selected = [topic.model_dump() for topic in request.selected_topics if topic.selected]
    by_unit: dict[str, list[dict]] = defaultdict(list)
    for topic in selected:
        by_unit[topic["unit"]].append(topic)
    question_count = sum(section.count for section in request.sections)
    weights = ({unit: weight for unit, weight in request.unit_weightage.items() if unit in by_unit and weight > 0}
               if request.unit_weightage else {unit: 100 // len(by_unit) for unit in by_unit})
    if not weights:
        raise ValueError("Selected units must have a positive unit weightage")
    # Preserve exact total for equal default weights.
    if not request.unit_weightage:
        remainder = 100 - sum(weights.values())
        for unit in list(weights)[:remainder]:
            weights[unit] += 1
    unit_counts = _largest_remainder(question_count, weights)
    unit_queue: list[str] = []
    while len(unit_queue) < question_count:
        for unit in by_unit:
            if unit_counts.get(unit, 0) > 0:
                unit_queue.append(unit)
                unit_counts[unit] -= 1
    difficulty_queue = _label_sequence(question_count, {
        "Easy": request.difficulty.easy,
        "Medium": request.difficulty.medium,
        "Hard": request.difficulty.hard,
    })
    bloom_weights = request.bloom_distribution or {
        "Remember": 15, "Understand": 25, "Apply": 25, "Analyze": 20, "Evaluate": 10, "Create": 5,
    }
    bloom_queue = _label_sequence(question_count, bloom_weights)
    topic_cursor: dict[str, int] = defaultdict(int)
    allocation: list[dict] = []
    slot = 0
    global_number = 1
    for section in request.sections:
        for position in range(1, section.count + 1):
            unit = unit_queue[slot]
            topics = by_unit[unit]
            topic = topics[topic_cursor[unit] % len(topics)]
            topic_cursor[unit] += 1
            allocation.append({
                "section": section.name,
                "section_position": position,
                "question_number": str(global_number),
                "unit": unit,
                "topic": topic["topic"],
                "subtopic": topic.get("subtopic"),
                "difficulty": difficulty_queue[slot],
                "bloom_level": bloom_queue[slot],
                "marks": section.marks,
                "question_type": section.question_type,
                "instructions": section.instructions,
                "has_choice": section.has_choice,
            })
            slot += 1
            global_number += 1
    unit_summary: dict[str, int] = defaultdict(int)
    difficulty_summary: dict[str, int] = defaultdict(int)
    bloom_summary: dict[str, int] = defaultdict(int)
    section_summary: list[dict] = []
    for item in allocation:
        unit_summary[item["unit"]] += 1
        difficulty_summary[item["difficulty"]] += 1
        bloom_summary[item["bloom_level"]] += 1
    for section in request.sections:
        section_summary.append({
            "name": section.name, "count": section.count, "marks_each": section.marks,
            "subtotal": section.count * section.marks, "question_type": section.question_type,
            "instructions": section.instructions, "has_choice": section.has_choice,
        })
    return {
        "allocation": allocation,
        "sections": section_summary,
        "unit_distribution": dict(unit_summary),
        "difficulty_distribution": dict(difficulty_summary),
        "bloom_distribution": dict(bloom_summary),
        "total_questions": question_count,
        "total_marks": request.total_marks,
    }

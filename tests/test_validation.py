from backend.app.validators.questions import duplicate_risk, validate_question


def test_semantic_duplicate_detection():
    duplicate, score, _ = duplicate_risk("Describe the operations performed on a stack.", ["Explain stack operations."])
    assert duplicate
    assert score >= 0.78


def test_portion_validation_rejects_outside_topic():
    result = validate_question(
        "Explain graph traversal using the prescribed method.", "UNIT IV", "Graph Traversal", 5,
        [{"unit": "UNIT II", "topic": "Stack", "selected": True}],
        "Graph traversal includes breadth first search.", [],
    )
    assert not result["passed"]
    assert not result["inside_selected_portion"]

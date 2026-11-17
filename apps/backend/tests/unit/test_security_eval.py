"""Unit tests for adversarial security benchmark and Ragas RAG evaluation."""

from pathlib import Path

from app.evaluation.ragas_eval import RagasEvaluator
from app.evaluation.security_eval import SecurityEvaluator


def test_adversarial_security_dataset_evaluation():
    """Verify adversarial security test cases achieve expected precision and recall."""
    evaluator = SecurityEvaluator()
    fixture_path = (
        Path(__file__).resolve().parents[1] / "fixtures" / "security_adversarial_dataset.json"
    )

    results = evaluator.evaluate_dataset(fixture_path)

    # 1. Prompt Injection
    pi_res = results["prompt_injections"]
    assert pi_res.recall == 1.0  # Caught 100% of injected prompts
    assert pi_res.false_positive_rate == 0.0  # Legitimate educational prompt passed
    assert pi_res.accuracy == 1.0

    # 2. Retrieval Injections
    ret_res = results["retrieval_injections"]
    assert ret_res.recall == 1.0
    assert ret_res.accuracy == 1.0

    # 3. Cross-Student Access
    cross_res = results["cross_student_access"]
    assert cross_res.recall == 1.0
    assert cross_res.accuracy == 1.0

    # 4. Unauthorized Tools
    tool_res = results["unauthorized_tools"]
    assert tool_res.recall == 1.0
    assert tool_res.accuracy == 1.0

    # 5. Unsafe Outputs
    out_res = results["unsafe_outputs"]
    assert out_res.recall == 1.0
    assert out_res.accuracy == 1.0

    # 6. PII Redaction
    pii_res = results["pii_redaction"]
    assert pii_res.recall == 1.0
    assert pii_res.false_positive_rate == 0.0


def test_ragas_evaluator_scoring():
    """Verify Ragas evaluator computes Context Precision, Recall, Faithfulness, and Relevancy."""
    evaluator = RagasEvaluator()

    sample_data = [
        {
            "question": "What is gradient descent?",
            "contexts": [
                "Gradient descent is an optimization algorithm used to minimize loss functions by iteratively moving in the direction of the negative gradient."
            ],
            "answer": "Gradient descent minimizes the loss function using the negative gradient direction.",
            "ground_truth": "Gradient descent is an optimization algorithm for finding the minimum of a function.",
        },
        {
            "question": "What is the chain rule in calculus?",
            "contexts": [
                "The chain rule provides a formula for computing the derivative of the composite of two or more functions."
            ],
            "answer": "The chain rule computes the derivative of composite functions.",
            "ground_truth": "The chain rule calculates derivatives of composite functions.",
        },
    ]

    report = evaluator.evaluate_dataset(sample_data)

    assert report.samples_evaluated == 2
    assert report.context_precision >= 0.50
    assert report.context_recall >= 0.50
    assert report.faithfulness >= 0.50
    assert report.answer_relevancy >= 0.50
    assert len(report.details) == 2

"""Automated intent classification benchmark and evaluation runner."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest
from app.core.config import RoutingSettings
from app.routing.intent_router import JevIntentRouter
from app.routing.taxonomy import IntentType

DATASET_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "intent_dataset.json"


@pytest.mark.asyncio
async def test_intent_classification_benchmark():
    """Run full measurable evaluation of the intent router across 50+ labeled examples."""
    assert DATASET_PATH.exists(), f"Dataset file not found at {DATASET_PATH}"

    with open(DATASET_PATH, encoding="utf-8") as f:
        dataset = json.load(f)

    assert len(dataset) >= 50, f"Evaluation requires at least 50 examples, found {len(dataset)}"

    settings = RoutingSettings(
        jev_enabled=False,  # Evaluates deterministic routing engine baseline
        confidence_high_threshold=0.70,
        confidence_low_threshold=0.40,
    )
    router = JevIntentRouter(settings)

    all_intents = [it.value for it in IntentType]
    true_positives = defaultdict(int)
    false_positives = defaultdict(int)
    false_negatives = defaultdict(int)
    confusion_matrix = defaultdict(lambda: defaultdict(int))

    total = len(dataset)
    correct = 0

    for item in dataset:
        text = item["text"]
        expected = item["expected_intent"]

        decision = await router.route(text)
        predicted = decision.intent.value

        confusion_matrix[expected][predicted] += 1

        if predicted == expected:
            correct += 1
            true_positives[expected] += 1
        else:
            false_negatives[expected] += 1
            false_positives[predicted] += 1

    accuracy = correct / total

    # Calculate per-class metrics
    class_metrics = {}
    f1_scores = []
    for intent in all_intents:
        tp = true_positives[intent]
        fp = false_positives[intent]
        fn = false_negatives[intent]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        class_metrics[intent] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }
        if tp + fn > 0:
            f1_scores.append(f1)

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

    # Print evaluation report
    print("\n" + "=" * 65)
    print(" SOCRATICAI INTENT ROUTER EVALUATION BENCHMARK REPORT")
    print("=" * 65)
    print(f"Total Test Samples: {total}")
    print(f"Overall Accuracy:   {accuracy * 100:.2f}% ({correct}/{total})")
    print(f"Macro-Averaged F1:  {macro_f1:.3f}")
    print("-" * 65)
    print(f"{'Intent':<22} | {'Precision':<9} | {'Recall':<7} | {'F1':<6} | {'Support'}")
    print("-" * 65)
    for intent, m in sorted(class_metrics.items()):
        if m["support"] > 0:
            print(
                f"{intent:<22} | {m['precision']:<9.3f} | {m['recall']:<7.3f} | {m['f1']:<6.3f} | {m['support']}"
            )
    print("=" * 65 + "\n")

    # Rigorous benchmark thresholds
    assert accuracy >= 0.85, f"Overall accuracy {accuracy:.2f} failed to meet 85% threshold."
    assert macro_f1 >= 0.80, f"Macro F1 {macro_f1:.2f} failed to meet 0.80 threshold."

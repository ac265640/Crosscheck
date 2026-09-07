"""
Evaluation harness.
Matches extracted facts to labeled ground-truth facts by:
  - Entity similarity (fuzzy) + attribute similarity + value match
Computes precision, recall, F1.
Prints a clean summary table to stdout.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rapidfuzz import fuzz

from backend.app.storage.repository import list_all_facts_with_embeddings
from backend.app.config import DB_PATH

LABELED_FACTS_PATH = Path(__file__).parent / "labeled_facts.json"

# Thresholds for matching
ENTITY_MATCH_THRESHOLD = 70    # rapidfuzz partial_ratio
ATTRIBUTE_MATCH_THRESHOLD = 60
VALUE_MATCH_THRESHOLD = 75


def normalize_value(v: str) -> str:
    """Strip commas and spaces for numeric comparison."""
    return re.sub(r"[,\s]", "", str(v)).lower()


def match_fact_to_label(extracted_fact, label: dict) -> bool:
    """Check whether an extracted fact matches a labeled fact."""
    entity_score = fuzz.partial_ratio(
        extracted_fact.entity.lower(), label["entity"].lower()
    )
    if entity_score < ENTITY_MATCH_THRESHOLD:
        return False

    attr_score = fuzz.partial_ratio(
        extracted_fact.attribute.lower(), label["attribute"].lower()
    )
    if attr_score < ATTRIBUTE_MATCH_THRESHOLD:
        return False

    val_score = fuzz.partial_ratio(
        normalize_value(extracted_fact.value),
        normalize_value(label["value"]),
    )
    if val_score < VALUE_MATCH_THRESHOLD:
        return False

    return True


def run_eval() -> None:
    print("=" * 60)
    print("FACT KNOWLEDGE LAYER — EVALUATION REPORT")
    print("=" * 60)

    # Load labeled facts
    with open(LABELED_FACTS_PATH) as f:
        labeled_facts = json.load(f)
    print(f"\nGround truth: {len(labeled_facts)} labeled facts\n")

    # Load extracted facts from DB
    all_pairs = list_all_facts_with_embeddings(DB_PATH)
    extracted_facts = [f for f, _ in all_pairs if f.verification_status != "extraction_failed"]
    print(f"Extracted facts in DB: {len(extracted_facts)}")
    print(f"  Verified: {sum(1 for f in extracted_facts if f.verification_status == 'verified')}")
    print(f"  Unverified: {sum(1 for f in extracted_facts if f.verification_status == 'unverified')}")
    print()

    # Match each labeled fact to extracted facts
    matched_labels = []
    missed_labels = []

    for label in labeled_facts:
        matched = False
        for ef in extracted_facts:
            if match_fact_to_label(ef, label):
                matched = True
                break
        if matched:
            matched_labels.append(label)
        else:
            missed_labels.append(label)

    # Precision: of extracted facts, how many match a label?
    true_positives = 0
    matched_label_set = set(id(l) for l in matched_labels)
    false_positives = []

    for ef in extracted_facts:
        matched_any = any(match_fact_to_label(ef, label) for label in labeled_facts)
        if matched_any:
            true_positives += 1
        # We can't easily flag FPs without reviewing all — skip for brevity

    # Metrics
    recall_num = len(matched_labels)
    recall_denom = len(labeled_facts)
    precision_num = true_positives
    precision_denom = len(extracted_facts) if extracted_facts else 1

    recall = recall_num / recall_denom if recall_denom else 0
    precision = precision_num / precision_denom if precision_denom else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

    print("-" * 60)
    print(f"{'Metric':<20} {'Value':>10}")
    print("-" * 60)
    print(f"{'Precision':<20} {precision:>10.1%}")
    print(f"{'Recall':<20} {recall:>10.1%}")
    print(f"{'F1 Score':<20} {f1:>10.1%}")
    print(f"{'True Positives':<20} {true_positives:>10}")
    print(f"{'Matched Labels':<20} {recall_num:>10}/{recall_denom}")
    print("-" * 60)

    if missed_labels:
        print(f"\n❌ MISSES ({len(missed_labels)} labeled facts the pipeline didn't find):")
        for label in missed_labels:
            print(f"  • {label['entity']} / {label['attribute']} = {label['value']} {label.get('unit', '')}")

    print("\n✅ MATCHED:")
    for label in matched_labels:
        print(f"  • {label['entity']} / {label['attribute']} = {label['value']} {label.get('unit', '')}")

    print("\n" + "=" * 60)
    print("Eval complete.")


if __name__ == "__main__":
    run_eval()

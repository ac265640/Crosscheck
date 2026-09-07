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

from backend.app.canonicalization.canonicalizer import is_same_entity

# Thresholds for matching
ATTRIBUTE_MATCH_THRESHOLD = 55


def match_value(extracted: str, labeled: str) -> bool:
    """Compare two values numerically if possible, otherwise by string similarity."""
    e_str = re.sub(r"[,\s%₹]", "", str(extracted)).strip().lower()
    l_str = re.sub(r"[,\s%₹]", "", str(labeled)).strip().lower()
    if e_str == l_str:
        return True
    try:
        e_float = float(e_str)
        l_float = float(l_str)
        return abs(e_float - l_float) < 0.05
    except ValueError:
        return fuzz.ratio(e_str, l_str) >= 75


def match_fact_to_label(extracted_fact, label: dict) -> bool:
    """Check whether an extracted fact matches a labeled fact."""
    if not is_same_entity(extracted_fact.entity, label["entity"]):
        return False

    attr_score = fuzz.token_sort_ratio(
        extracted_fact.attribute.lower(), label["attribute"].lower()
    )
    # Also check substring / containment
    is_attr_contained = (
        label["attribute"].lower() in extracted_fact.attribute.lower()
        or extracted_fact.attribute.lower() in label["attribute"].lower()
    )
    if attr_score < ATTRIBUTE_MATCH_THRESHOLD and not is_attr_contained:
        return False

    return match_value(extracted_fact.value, label["value"])


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

    # Precision on candidate target claims (facts matching target entity & attribute)
    target_tp = 0
    target_fp = 0

    for ef in extracted_facts:
        matching_targets = [
            l for l in labeled_facts
            if is_same_entity(ef.entity, l["entity"])
            and (
                fuzz.token_sort_ratio(ef.attribute.lower(), l["attribute"].lower()) >= 65
                or l["attribute"].lower() in ef.attribute.lower()
                or ef.attribute.lower() in l["attribute"].lower()
            )
        ]
        if matching_targets:
            if any(match_value(ef.value, l["value"]) for l in matching_targets):
                target_tp += 1
            else:
                target_fp += 1

    # Metrics
    recall_num = len(matched_labels)
    recall_denom = len(labeled_facts)
    precision_num = target_tp
    precision_denom = (target_tp + target_fp) if (target_tp + target_fp) > 0 else 1

    recall = recall_num / recall_denom if recall_denom else 0
    precision = precision_num / precision_denom
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0

    total_extracted = len(extracted_facts)
    verified_count = sum(1 for f in extracted_facts if f.verification_status == "verified")
    verification_rate = verified_count / total_extracted if total_extracted else 0

    print("-" * 60)
    print(f"{'Metric':<25} {'Value':>10}")
    print("-" * 60)
    print(f"{'Target Claim Precision':<25} {precision:>10.1%}")
    print(f"{'Ground Truth Recall':<25} {recall:>10.1%}")
    print(f"{'F1 Score':<25} {f1:>10.1%}")
    print(f"{'Evidence Verified Rate':<25} {verification_rate:>10.1%}")
    print(f"{'Matched Ground Truth':<25} {recall_num:>10}/{recall_denom}")
    print(f"{'Total Facts in DB':<25} {total_extracted:>10}")
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

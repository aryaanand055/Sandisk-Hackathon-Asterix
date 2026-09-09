#!/usr/bin/env python3
"""
Grade model discoveries against planted ground truth rules.

This is the ONLY script that reads ground_truth_rules.json.
It compares the model's discovered feature importances and interaction
combinations against the known planted rules, computing:
  * Rule discovery recall (which planted rules were detected)
  * Feature detection coverage (which rule-relevant features appeared in top-K)
  * Interaction match quality (do discovered combos match planted conditions)

Usage
-----
    python grade_against_ground_truth.py [--rules FILE] [--results FILE]
                                         [--interactions FILE]
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Set, Tuple


# =========================================================================
# Rule Parsing
# =========================================================================

def _extract_rule_features(rule: Dict) -> Set[str]:
    """Extract the set of feature names involved in a rule's conditions."""
    return {c["field"] for c in rule["conditions"]}


def _format_condition(cond: Dict) -> str:
    """Human-readable condition string."""
    return f"{cond['field']} {cond['op']} {cond['value']}"


# =========================================================================
# Feature Coverage Grading
# =========================================================================

def grade_feature_coverage(
    rules: List[Dict],
    importances: List[Dict],
    top_k: int = 5,
) -> Dict[str, Any]:
    """Check whether rule-relevant features appear in the model's top-K
    important features.

    Returns per-rule and aggregate coverage stats.
    """
    top_features = {
        entry["feature"] for entry in importances[:top_k]
    }

    per_rule = []
    total_features = 0
    detected_features = 0

    for rule in rules:
        rule_feats = _extract_rule_features(rule)
        matched = rule_feats & top_features
        missed = rule_feats - top_features

        total_features += len(rule_feats)
        detected_features += len(matched)

        per_rule.append({
            "rule_id": rule["id"],
            "description": rule.get("description", ""),
            "effect_type": rule["effect"]["type"],
            "rule_features": sorted(rule_feats),
            "matched_features": sorted(matched),
            "missed_features": sorted(missed),
            "coverage": len(matched) / len(rule_feats) if rule_feats else 0.0,
            "fully_detected": len(missed) == 0,
        })

    return {
        "top_k": top_k,
        "top_features": sorted(top_features),
        "per_rule": per_rule,
        "aggregate_feature_recall": (
            detected_features / total_features if total_features > 0 else 0.0
        ),
    }


# =========================================================================
# Interaction Match Grading
# =========================================================================

def _rule_matches_interaction(
    rule: Dict,
    interaction: Dict,
    original_csv_path: str = None,
) -> Tuple[bool, float]:
    """Check if an interaction's feature set aligns with a rule's conditions.

    Returns (is_match, match_score) where match_score is the fraction of
    rule condition features covered by the interaction's feature set.
    """
    rule_feats = _extract_rule_features(rule)
    interaction_feats = set(interaction["features"])

    overlap = rule_feats & interaction_feats
    if not overlap:
        return False, 0.0

    score = len(overlap) / len(rule_feats)
    # Require at least partial overlap to count as a match
    is_match = score >= 0.5
    return is_match, score


def grade_interactions(
    rules: List[Dict],
    interactions: List[Dict],
) -> Dict[str, Any]:
    """Match discovered interactions against planted rules.

    For each planted failure rule, find the best-matching discovered
    interaction (if any).
    """
    # Only grade failure-related rules (failure_multiplier)
    failure_rules = [
        r for r in rules
        if r["effect"]["type"] == "failure_multiplier"
    ]

    per_rule = []
    rules_detected = 0

    for rule in failure_rules:
        rule_feats = _extract_rule_features(rule)
        best_match = None
        best_score = 0.0

        for inter in interactions:
            is_match, score = _rule_matches_interaction(rule, inter)
            if is_match and score > best_score:
                best_score = score
                best_match = inter

        detected = best_match is not None
        if detected:
            rules_detected += 1

        entry = {
            "rule_id": rule["id"],
            "description": rule.get("description", ""),
            "rule_features": sorted(rule_feats),
            "detected": detected,
            "match_score": round(best_score, 2),
        }
        if best_match:
            cond_str = " AND ".join(
                f"{c['feature']}={c['value']}"
                for c in best_match["conditions"]
            )
            entry["matched_interaction"] = cond_str
            entry["interaction_lift"] = best_match["lift"]
            entry["interaction_support"] = best_match["support"]

        per_rule.append(entry)

    return {
        "total_failure_rules": len(failure_rules),
        "rules_detected": rules_detected,
        "rule_recall": (
            rules_detected / len(failure_rules) if failure_rules else 0.0
        ),
        "per_rule": per_rule,
    }


# =========================================================================
# Overall Grading Score
# =========================================================================

def compute_overall_grade(
    feature_grade: Dict,
    interaction_grade: Dict,
) -> Dict[str, Any]:
    """Composite grading score (0-100).

    Weighting:
        Feature coverage recall: 40%
        Rule interaction recall: 60%
    """
    feat_recall = feature_grade["aggregate_feature_recall"]
    rule_recall = interaction_grade["rule_recall"]

    composite = 0.40 * feat_recall + 0.60 * rule_recall
    score = round(composite * 100, 1)

    if score >= 80:
        grade_letter = "A"
        assessment = "Excellent -- model reliably identifies planted failure patterns"
    elif score >= 60:
        grade_letter = "B"
        assessment = "Good -- model captures most failure patterns"
    elif score >= 40:
        grade_letter = "C"
        assessment = "Fair -- model captures some patterns but misses key interactions"
    elif score >= 20:
        grade_letter = "D"
        assessment = "Poor -- significant failure patterns not detected"
    else:
        grade_letter = "F"
        assessment = "Failing -- model does not detect planted patterns"

    return {
        "composite_score": score,
        "grade": grade_letter,
        "assessment": assessment,
        "feature_recall_weight": 0.40,
        "interaction_recall_weight": 0.60,
        "feature_recall": round(feat_recall, 4),
        "rule_recall": round(rule_recall, 4),
    }


# =========================================================================
# Reporting (ASCII-only)
# =========================================================================

def _print_section(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_grading_report(
    feature_grade: Dict,
    interaction_grade: Dict,
    overall: Dict,
    rules: List[Dict],
) -> None:
    """Print the full grading report."""
    _print_section("GRADING REPORT -- Ground Truth vs Model Discoveries")

    # ── Feature Coverage ──
    _print_section(
        f"Feature Coverage (top-{feature_grade['top_k']} model features)"
    )
    print(f"\n  Model's top features: {', '.join(feature_grade['top_features'])}")
    print(f"\n  {'Rule':<10s} {'Coverage':>10s} {'Detected?':>10s} "
          f"{'Matched':<25s} {'Missed':<25s}")
    print(f"  {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 25} {'-' * 25}")

    for entry in feature_grade["per_rule"]:
        matched = ", ".join(entry["matched_features"]) or "(none)"
        missed = ", ".join(entry["missed_features"]) or "(none)"
        det = "YES" if entry["fully_detected"] else "partial" if entry["coverage"] > 0 else "NO"
        print(
            f"  {entry['rule_id']:<10s} {entry['coverage']:>9.0%} "
            f"{det:>10s} {matched:<25s} {missed:<25s}"
        )
    print(
        f"\n  Aggregate feature recall: "
        f"{feature_grade['aggregate_feature_recall']:.1%}"
    )

    # ── Interaction Matching ──
    _print_section("Interaction Matching (failure rules only)")
    print(
        f"\n  {interaction_grade['rules_detected']} / "
        f"{interaction_grade['total_failure_rules']} failure rules detected "
        f"via interaction analysis"
    )
    print(f"\n  {'Rule':<10s} {'Detected?':>10s} {'Match':>6s} "
          f"{'Lift':>6s} {'Matched Interaction':<35s}")
    print(f"  {'-' * 10} {'-' * 10} {'-' * 6} {'-' * 6} {'-' * 35}")

    for entry in interaction_grade["per_rule"]:
        det = "YES" if entry["detected"] else "NO"
        score = f"{entry['match_score']:.0%}" if entry["detected"] else "-"
        lift = f"{entry.get('interaction_lift', 0):.1f}x" if entry["detected"] else "-"
        matched = entry.get("matched_interaction", "-")
        if len(matched) > 34:
            matched = matched[:31] + "..."
        print(
            f"  {entry['rule_id']:<10s} {det:>10s} {score:>6s} "
            f"{lift:>6s} {matched:<35s}"
        )

    # ── Rule Descriptions ──
    _print_section("Planted Rules Reference")
    for rule in rules:
        cond_str = " AND ".join(_format_condition(c) for c in rule["conditions"])
        effect_desc = (
            f"{rule['effect']['type']}({rule['effect']['target']}) "
            f"x{rule['effect']['value']}"
        )
        print(f"  {rule['id']}: {cond_str}")
        print(f"    -> {effect_desc}")
        print(f"    {rule.get('description', '')}")
        print()

    # ── Overall Score ──
    _print_section("OVERALL GRADE")
    print(f"\n  Composite Score : {overall['composite_score']}/100")
    print(f"  Letter Grade    : {overall['grade']}")
    print(f"  Assessment      : {overall['assessment']}")
    print(f"\n  Breakdown:")
    print(f"    Feature Recall ({overall['feature_recall_weight']:.0%} weight) : "
          f"{overall['feature_recall']:.1%}")
    print(f"    Rule Recall    ({overall['interaction_recall_weight']:.0%} weight) : "
          f"{overall['rule_recall']:.1%}")


# =========================================================================
# Main
# =========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grade model discoveries against ground truth rules."
    )
    parser.add_argument(
        "--rules", default="ground_truth_rules.json",
        help="Ground truth rules JSON (default: ground_truth_rules.json)",
    )
    parser.add_argument(
        "--results", default="model_results.json",
        help="Model results JSON from train_baseline.py",
    )
    parser.add_argument(
        "--interactions", default="discovered_interactions.json",
        help="Discovered interactions JSON from interaction_analysis.py",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Consider top-K features for coverage grading (default: 5)",
    )
    parser.add_argument(
        "--output", default="grading_report.json",
        help="Output JSON for grading results",
    )
    args = parser.parse_args()

    # Load inputs
    with open(args.rules, "r") as fh:
        rules_data = json.load(fh)
    rules = rules_data["rules"]

    with open(args.results, "r") as fh:
        results = json.load(fh)

    with open(args.interactions, "r") as fh:
        interactions_data = json.load(fh)
    interactions = interactions_data["interactions"]

    importances = results["feature_importances"]

    # Grade
    feature_grade = grade_feature_coverage(rules, importances, top_k=args.top_k)
    interaction_grade = grade_interactions(rules, interactions)
    overall = compute_overall_grade(feature_grade, interaction_grade)

    # Report
    print_grading_report(feature_grade, interaction_grade, overall, rules)

    # Export
    report_payload = {
        "feature_coverage": feature_grade,
        "interaction_matching": interaction_grade,
        "overall": overall,
    }
    with open(args.output, "w") as fh:
        json.dump(report_payload, fh, indent=2)
    print(f"\n  -> {args.output} written")
    print("\nDone.")


if __name__ == "__main__":
    main()

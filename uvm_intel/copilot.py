#!/usr/bin/env python3
"""
AI Verification Copilot powered by Google Gemini.

Constructs a rich contextual prompt from the complete dashboard analysis payload
and queries Google Gemini API to answer user natural language questions.
"""

import json
import os
from typing import Any, Dict, Optional

# Try loading .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.expanduser("~/.env"))
except ImportError:
    pass


def build_dashboard_context(analysis: Dict[str, Any]) -> str:
    """Format complete dashboard results into a structured Markdown text for Gemini."""
    summary = analysis.get("summary", {})
    risk_model = analysis.get("risk_model", {})
    fingerprints = analysis.get("fingerprints", {})
    pareto = analysis.get("pareto", {})
    recommendations = analysis.get("recommendations", {})
    config_diff = analysis.get("config_diff", {})
    failure_by_field = analysis.get("failure_by_field", [])

    lines = []
    lines.append("=== VERIFICATION DATASET DASHBOARD RESULTS ===")
    lines.append(f"- Total Runs: {summary.get('n_runs', 0):,}")
    lines.append(f"- Passed Runs: {summary.get('n_pass', 0):,}")
    lines.append(f"- Failed Runs: {summary.get('n_fail', 0):,} ({summary.get('fail_rate', 0)*100:.2f}% failure rate)")
    lines.append(f"- Error Log Lines: {summary.get('n_error_lines', 0):,}")

    if summary.get("error_tag_distribution"):
        lines.append(f"- Failure Error Tags: {json.dumps(summary.get('error_tag_distribution'))}")

    if summary.get("metric_stats"):
        lines.append(f"- Execution & Performance Stats: {json.dumps(summary.get('metric_stats'))}")

    lines.append("\n=== RISK CLASSIFIER & SHAP ATTRIBUTION ===")
    metrics = risk_model.get("metrics", {})
    lines.append(f"- Model Metrics: ROC-AUC={metrics.get('roc_auc')}, PR-AUC={metrics.get('pr_auc')}, Accuracy={metrics.get('accuracy')}, F1={metrics.get('f1')}")

    shap = risk_model.get("shap_importance", [])
    if shap:
        shap_summary = [{ "feature": s["feature"], "importance_pct": s.get("importance_pct"), "direction": s.get("direction") } for s in shap[:8]]
        lines.append(f"- Top Feature Importance (SHAP): {json.dumps(shap_summary)}")

    lines.append("\n=== FAILURE FINGERPRINTS & CLUSTERING ===")
    lines.append(f"- Failure Clusters Count: {fingerprints.get('n_clusters', 0)}")
    lines.append(f"- Deterministic Clusters: {fingerprints.get('deterministic_clusters', [])}")
    clusters = fingerprints.get("clusters", [])
    if clusters:
        cluster_summary = [{
            "cluster_id": c.get("cluster_id"),
            "size": c.get("size"),
            "determinism": c.get("determinism"),
            "classification": c.get("classification"),
            "dominant_tag": c.get("dominant_tag"),
            "representative_template": c.get("representative_template")
        } for c in clusters[:5]]
        lines.append(f"- Top Failure Clusters: {json.dumps(cluster_summary)}")

    lines.append("\n=== PARETO TRADEOFF FRONTIER ===")
    lines.append(f"- Frontier Points Count: {pareto.get('n_frontier', 0)}")
    if pareto.get("knee_config"):
        lines.append(f"- Knee Operating Point (Optimal Balance): {json.dumps(pareto.get('knee_config'))}")
    if pareto.get("best_safe_config"):
        lines.append(f"- Best Low-Risk Safe Config: {json.dumps(pareto.get('best_safe_config'))}")
    if pareto.get("max_throughput_config"):
        lines.append(f"- Max Throughput Config: {json.dumps(pareto.get('max_throughput_config'))}")

    lines.append("\n=== OPTIMAL CONFIG RECOMMENDATIONS ===")
    if recommendations and not recommendations.get("skipped"):
        rec_cfg = recommendations.get("recommendation", {}).get("config", {})
        rec_risk = recommendations.get("recommendation", {}).get("predicted_risk")
        lines.append(f"- Recommended Config: {json.dumps(rec_cfg)}")
        lines.append(f"- Recommended Config Predicted Risk: {rec_risk}")

    if failure_by_field:
        field_summary = [{ "field": f["field"], "spread": f["spread"], "top_level": f["levels"][0] if f["levels"] else None } for f in failure_by_field[:5]]
        lines.append(f"\n=== FIELD FAILURE LIFT ===\n{json.dumps(field_summary)}")

    return "\n".join(lines)


def query_gemini_copilot(
    question: str,
    analysis: Dict[str, Any],
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """Query Gemini LLM with full context from the dashboard analysis."""
    key = api_key or os.environ.get("GEMINI_API_KEY")

    context_str = build_dashboard_context(analysis)

    system_instruction = (
        "You are an expert AI Verification Assistant for UVM VLSI Verification Engineers and System Designers. "
        "You have full access to the complete dashboard analysis payload from the test corpus, including ML risk model "
        "SHAP feature importance, failure fingerprints/clustering, Pareto throughput vs risk frontiers, configuration diffs, "
        "and automated optimizer recommendations.\n"
        "Provide direct, concise, clear, and actionable answers to the engineer's question in crisp GitHub Markdown format. "
        "Use bullet points, bold key settings, and highlight concrete numbers."
    )

    prompt = (
        f"Context:\n{context_str}\n\n"
        f"User Question: {question}"
    )

    if not key:
        # Fallback response when key is not configured yet
        return {
            "gemini_used": False,
            "answer": (
                "⚠️ **Gemini API Key Missing**\n\n"
                "Please enter your **Gemini API Key** in the input field at the top of the AI Copilot tab or add `GEMINI_API_KEY` to your environment / `.env` file.\n\n"
                "### Summary of Dashboard Analysis Results:\n" +
                _rule_based_fallback(question, analysis)
            )
        }

    try:
        from google import genai
        client = genai.Client(api_key=key)

        # Try gemini-2.5-flash or gemini-2.0-flash
        model_names = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        response_text = None
        used_model = None
        last_err = None

        for m_name in model_names:
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=f"{system_instruction}\n\n{prompt}"
                )
                if response and response.text:
                    response_text = response.text
                    used_model = m_name
                    break
            except Exception as e:
                last_err = e
                continue

        if not response_text:
            raise RuntimeError(f"Gemini API call failed across models: {last_err}")

        return {
            "gemini_used": True,
            "model": used_model,
            "answer": response_text
        }

    except Exception as exc:
        return {
            "gemini_used": False,
            "error": str(exc),
            "answer": (
                f"⚠️ **Gemini API Error**: `{exc}`\n\n"
                "### Automated Dashboard Analysis Synthesis:\n" +
                _rule_based_fallback(question, analysis)
            )
        }


def _rule_based_fallback(question: str, analysis: Dict[str, Any]) -> str:
    summary = analysis.get("summary", {})
    risk_model = analysis.get("risk_model", {})
    fingerprints = analysis.get("fingerprints", {})
    recommendations = analysis.get("recommendations", {})

    n_runs = summary.get("n_runs", 0)
    fail_rate = summary.get("fail_rate", 0) * 100
    top_features = [f["feature"] for f in risk_model.get("shap_importance", [])[:3]]
    n_clusters = fingerprints.get("n_clusters", 0)
    rec_config = recommendations.get("recommendation", {}).get("config", {}) if isinstance(recommendations, dict) else {}

    res = []
    res.append(f"• **Corpus Size**: {n_runs:,} runs evaluated ({summary.get('n_pass', 0):,} pass, {summary.get('n_fail', 0):,} fail).")
    res.append(f"• **Observed Failure Rate**: {fail_rate:.2f}%.")
    if top_features:
        res.append(f"• **Primary Failure Risk Drivers**: `{', '.join(top_features)}`.")
    if n_clusters > 0:
        res.append(f"• **Failure Fingerprint Clusters**: {n_clusters} failure pattern(s) identified.")
    if rec_config:
        rec_str = ", ".join([f"`{k}={v}`" for k, v in list(rec_config.items())[:5]])
        res.append(f"• **Recommended Optimal Setting**: {rec_str}.")

    return "\n\n".join(res)

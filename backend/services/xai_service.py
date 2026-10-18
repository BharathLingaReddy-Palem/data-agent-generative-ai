"""
xai_service.py — Explainable AI (XAI) & Interpretability Service
================================================================
Provides transparent feature importance and prediction explanations
using SHAP (SHapley Additive exPlanations) and Permutation Importance.

Features:
- Global feature importance (Mean |SHAP| or Permutation score)
- Feature directional impact (e.g. Higher values increase target)
- Local explanation for individual rows / predictions
- Formatted Plotly-ready bar chart specifications
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

logger = logging.getLogger(__name__)

# Try importing shap; provide graceful fallback if not present
try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False
    logger.info("SHAP not installed; using Sklearn Permutation Importance as primary XAI method.")


def compute_feature_importance(
    model: Any,
    X_train: Any,
    X_test: Any,
    y_test: Any,
    feature_names: List[str],
    task_type: str = "classification",
    top_n: int = 10,
) -> Dict[str, Any]:
    """
    Computes global feature importance using SHAP TreeExplainer where possible,
    falling back to Permutation Importance and Model Feature Importances.
    """
    importance_dict: Dict[str, float] = {}
    method_used = "permutation_importance"

    # Convert to pure numpy to avoid warnings
    X_train_arr = np.asarray(X_train)
    X_test_arr = np.asarray(X_test)
    y_test_arr = np.asarray(y_test)

    # 1. Try Fast SHAP TreeExplainer for tree models
    if HAS_SHAP and hasattr(model, "feature_importances_"):
        try:
            eval_set = X_test_arr[:min(30, len(X_test_arr))]
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(eval_set, check_additivity=False)

            if isinstance(shap_values, list):  # Multiclass
                mean_abs = np.mean([np.abs(sv).mean(axis=0) for sv in shap_values], axis=0)
            elif isinstance(shap_values, np.ndarray):
                mean_abs = np.abs(shap_values).mean(axis=0)
            else:
                mean_abs = None

            if mean_abs is not None:
                for name, imp in zip(feature_names[:len(mean_abs)], mean_abs):
                    importance_dict[name] = round(float(imp), 4)
                method_used = "shap_tree"
        except Exception as e:
            logger.info(f"TreeExplainer skipped: {e}. Falling back to permutation importance.")

    # 2. Fallback to Permutation Importance
    if not importance_dict:
        try:
            n_eval = min(60, len(X_test_arr))
            X_eval = X_test_arr[:n_eval]
            y_eval = y_test_arr[:n_eval]

            perm = permutation_importance(
                model,
                X_eval,
                y_eval,
                n_repeats=3,
                random_state=42,
                scoring="f1_macro" if task_type == "classification" else "r2",
            )
            for name, imp in zip(feature_names[:len(perm.importances_mean)], perm.importances_mean):
                importance_dict[name] = round(float(max(0.0, imp)), 4)
            method_used = "permutation_importance"
        except Exception as e:
            logger.warning(f"Permutation importance fallback: {e}")
            if hasattr(model, "feature_importances_"):
                for name, imp in zip(feature_names[:len(model.feature_importances_)], model.feature_importances_):
                    importance_dict[name] = round(float(imp), 4)
                method_used = "feature_importances"
            elif hasattr(model, "coef_"):
                coefs = np.abs(model.coef_).flatten()
                for name, imp in zip(feature_names[:len(coefs)], coefs):
                    importance_dict[name] = round(float(imp), 4)
                method_used = "linear_coefficients"

    # Sort and rank top N
    sorted_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]
    total_val = sum(v for _, v in sorted_features) or 1.0

    ranked_list = []
    for rank, (feat, val) in enumerate(sorted_features, 1):
        pct_weight = round((val / total_val) * 100, 1)
        ranked_list.append({
            "rank": rank,
            "feature": feat,
            "importance_score": val,
            "relative_percentage": pct_weight,
            "impact_narrative": f"Feature '{feat}' has importance score {val:.4f}; {pct_weight}% of the displayed importance total. This is not a percentage of predictions or a causal effect.",
        })

    # Plotly bar chart config
    plotly_chart = {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "x": [item["importance_score"] for item in reversed(ranked_list)],
                "y": [item["feature"] for item in reversed(ranked_list)],
                "marker": {"color": "#00ff88"},
            }
        ],
        "layout": {
            "title": f"Top Drivers ({method_used.upper()})",
            "xaxis": {"title": "Importance Score"},
            "yaxis": {"title": "Feature"},
            "template": "plotly_dark",
            "margin": {"l": 120, "r": 20, "t": 40, "b": 40},
        },
    }

    return {
        "method": method_used,
        "top_features": ranked_list,
        "chart": plotly_chart,
    }

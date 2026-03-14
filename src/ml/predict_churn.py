"""
predict_churn.py
════════════════
ML Pipeline: Train a Random Forest model on Silver data and store
churn predictions into a Gold table (gold.churn_predictions).

Pipeline flow:
    silver.ecommerce_clean  →  train / predict  →  gold.churn_predictions

Features are aligned with the warehouse column naming convention
(lowercase, no underscores for multi-word columns).

Usage:
    python -m src.ml.predict_churn            # train + predict + store
    python -m src.ml.predict_churn --predict   # predict only (load saved model)
"""

import os
import sys
import uuid
import warnings
from datetime import datetime
from pathlib import Path

import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)
from sqlalchemy import text

warnings.filterwarnings("ignore")

# ── Ensure project root is on path ────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.db.connection import get_engine, ensure_schemas

# ── Paths ─────────────────────────────────────────────────
MODEL_DIR = _PROJECT_ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)
MODEL_PATH = MODEL_DIR / "churn_rf_model.pkl"

REPORTS_DIR = _PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ── Schema names from env ─────────────────────────────────
SILVER_SCHEMA = os.getenv("SILVER_SCHEMA", "silver")
GOLD_SCHEMA = os.getenv("GOLD_SCHEMA", "gold")
BRONZE_SCHEMA = os.getenv("BRONZE_SCHEMA", "bronze")

# ── Feature columns used for training ─────────────────────
# These correspond to silver.ecommerce_clean columns.
# Categoricals that need encoding: preferedordercat, preferredpaymentmode
# Already encoded in silver: preferredlogindevice_encoded, gender_encoded,
#                             maritalstatus_encoded
NUMERIC_FEATURES = [
    "tenure",
    "citytier",
    "warehousetohome",
    "hourspendonapp",
    "numberofdeviceregistered",
    "satisfactionscore",
    "numberofaddress",
    "complain",
    "orderamounthikefromlastyear",
    "couponused",
    "ordercount",
    "daysincelastorder",
    "cashbackamount",
]

# Pre-encoded in silver (by transform_to_silver.py)
PRE_ENCODED_FEATURES = [
    "preferredlogindevice_encoded",
    "gender_encoded",
    "maritalstatus_encoded",
]

# Categoricals we need to encode ourselves
CATEGORICALS_TO_ENCODE = [
    "preferedordercat",
    "preferredpaymentmode",
]

TARGET = "churn"


# ════════════════════════════════════════════════════════════
# 1. LOAD DATA FROM SILVER
# ════════════════════════════════════════════════════════════

def load_silver_data(engine) -> pd.DataFrame:
    """Read the cleaned data from silver.ecommerce_clean."""
    with engine.connect() as conn:
        df = pd.read_sql(
            text(f"SELECT * FROM {SILVER_SCHEMA}.ecommerce_clean"),
            conn,
        )
    print(f"  📥  Loaded {len(df):,} rows from {SILVER_SCHEMA}.ecommerce_clean")
    return df


# ════════════════════════════════════════════════════════════
# 2. PREPARE FEATURES
# ════════════════════════════════════════════════════════════

def prepare_features(df: pd.DataFrame) -> tuple:
    """
    Prepare feature matrix X and target y from Silver data.
    Returns (X, y, encoders_dict, feature_columns_list).
    """
    work = df.copy()

    # ── Fix inconsistent category names (same as reference) ──
    if "preferedordercat" in work.columns:
        work.loc[work["preferedordercat"] == "Mobile", "preferedordercat"] = "Mobile Phone"

    if "preferredpaymentmode" in work.columns:
        work.loc[work["preferredpaymentmode"] == "COD", "preferredpaymentmode"] = "Cash on Delivery"
        work.loc[work["preferredpaymentmode"] == "CC", "preferredpaymentmode"] = "Credit Card"

    # ── Encode remaining categoricals ────────────────────────
    encoders = {}
    for col in CATEGORICALS_TO_ENCODE:
        if col in work.columns:
            le = LabelEncoder()
            work[f"{col}_encoded"] = le.fit_transform(work[col].astype(str))
            encoders[col] = le

    # ── Build feature list ───────────────────────────────────
    encoded_cat_features = [f"{c}_encoded" for c in CATEGORICALS_TO_ENCODE if c in work.columns]
    feature_cols = NUMERIC_FEATURES + PRE_ENCODED_FEATURES + encoded_cat_features

    # Keep only columns that actually exist
    feature_cols = [c for c in feature_cols if c in work.columns]

    X = work[feature_cols].copy()
    y = work[TARGET].astype(int)

    # ── Fill any remaining NaN ───────────────────────────────
    for col in X.columns:
        if X[col].isna().any():
            X[col] = X[col].fillna(X[col].median())

    print(f"  🧮  Feature matrix: {X.shape[0]} rows × {X.shape[1]} features")
    print(f"  📋  Features: {feature_cols}")

    return X, y, encoders, feature_cols


# ════════════════════════════════════════════════════════════
# 3. TRAIN MODEL
# ════════════════════════════════════════════════════════════

def train_model(X: pd.DataFrame, y: pd.Series, feature_cols: list) -> tuple:
    """
    Train a Random Forest classifier with class-imbalance handling.
    Returns (model, scaler, metrics_dict).
    """
    resampled = False
    original_size = len(X)

    # ── Handle class imbalance ───────────────────────────────
    try:
        from imblearn.combine import SMOTETomek
        smt = SMOTETomek(random_state=42)
        X_res, y_res = smt.fit_resample(X, y)
        resampled = True
        print(f"  SMOTETomek resampling: {len(X)} -> {len(X_res)} rows")
    except ImportError:
        print("  imbalanced-learn not installed, skipping SMOTETomek")
        X_res, y_res = X, y

    # ── Train/test split ─────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X_res, y_res, test_size=0.30, random_state=42
    )

    # ── Scale features ───────────────────────────────────────
    scaler = MinMaxScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ── Train Random Forest ──────────────────────────────────
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    # ── Evaluate ─────────────────────────────────────────────
    metrics = evaluate_model(
        model, scaler, X_train, X_test, y_train, y_test,
        feature_cols, original_size, len(X_res), resampled,
    )

    print(f"  Train accuracy : {metrics['train_accuracy']:.4f}")
    print(f"  Test  accuracy : {metrics['test_accuracy']:.4f}")
    print(f"  Precision      : {metrics['precision']:.4f}")
    print(f"  Recall         : {metrics['recall']:.4f}")
    print(f"  F1-Score       : {metrics['f1_score']:.4f}")
    print(f"  ROC-AUC        : {metrics['roc_auc']:.4f}")

    return model, scaler, metrics


def _get_eval_data(model, scaler, X_train, X_test, y_train, y_test):
    """Compute predictions needed for plots and metrics."""
    X_train_scaled = scaler.transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    return {
        "y_train": y_train,
        "y_test": y_test,
        "y_train_pred": model.predict(X_train_scaled),
        "y_test_pred": model.predict(X_test_scaled),
        "y_test_proba": model.predict_proba(X_test_scaled)[:, 1],
    }


def evaluate_model(
    model, scaler,
    X_train, X_test, y_train, y_test,
    feature_cols, original_size, resampled_size, resampled,
) -> dict:
    """
    Compute all evaluation metrics for the trained model.
    Returns a comprehensive metrics dictionary.
    """
    X_train_scaled = scaler.transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    y_train_pred = model.predict(X_train_scaled)
    y_test_pred = model.predict(X_test_scaled)
    y_test_proba = model.predict_proba(X_test_scaled)[:, 1]

    # Confusion matrix
    cm = confusion_matrix(y_test, y_test_pred)
    tn, fp, fn, tp = cm.ravel()

    # Feature importance
    importances = model.feature_importances_
    feat_imp = sorted(
        zip(feature_cols, importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )

    # Classification report (as dict)
    cls_report = classification_report(y_test, y_test_pred, output_dict=True)

    metrics = {
        # ── Dataset info ──────────────────────────────
        "dataset": {
            "original_rows": original_size,
            "resampled_rows": resampled_size,
            "resampling_applied": resampled,
            "resampling_method": "SMOTETomek" if resampled else "None",
            "test_size": 0.30,
            "train_rows": len(X_train),
            "test_rows": len(X_test),
        },
        # ── Model config ─────────────────────────────
        "model": {
            "algorithm": "RandomForestClassifier",
            "n_estimators": 100,
            "max_depth": 15,
            "random_state": 42,
            "scaler": "MinMaxScaler",
            "n_features": len(feature_cols),
            "features": feature_cols,
        },
        # ── Core metrics ─────────────────────────────
        "train_accuracy": round(accuracy_score(y_train, y_train_pred), 4),
        "test_accuracy": round(accuracy_score(y_test, y_test_pred), 4),
        "precision": round(precision_score(y_test, y_test_pred), 4),
        "recall": round(recall_score(y_test, y_test_pred), 4),
        "f1_score": round(f1_score(y_test, y_test_pred), 4),
        "roc_auc": round(roc_auc_score(y_test, y_test_proba), 4),
        # ── Confusion matrix ────────────────────────
        "confusion_matrix": {
            "true_negatives": int(tn),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_positives": int(tp),
        },
        # ── Per-class report ────────────────────────
        "classification_report": cls_report,
        # ── Feature importance (sorted desc) ────────
        "feature_importance": [
            {"feature": name, "importance": round(imp, 4)}
            for name, imp in feat_imp
        ],
        # ── Timestamps ──────────────────────────────
        "trained_at": datetime.now().isoformat(),
    }

    return metrics


def save_evaluation_report(metrics: dict, eval_data: dict = None) -> tuple:
    """
    Save evaluation metrics to:
      - reports/model_evaluation.json  (machine-readable)
      - reports/model_evaluation.md    (human-readable, for evaluator)
      - reports/*.png                  (plots embedded in the report)
    Returns (json_path, md_path).
    """
    json_path = REPORTS_DIR / "model_evaluation.json"
    md_path = REPORTS_DIR / "model_evaluation.md"

    # ── JSON ──────────────────────────────────────────────────
    with open(json_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)

    # ── Generate plots ────────────────────────────────────────
    plot_paths = {}
    if eval_data is not None:
        plot_paths = generate_evaluation_plots(metrics, eval_data)

    # ── Markdown report ───────────────────────────────────────
    cm = metrics["confusion_matrix"]
    ds = metrics["dataset"]
    model_info = metrics["model"]
    feat_imp = metrics["feature_importance"]
    cls_rpt = metrics["classification_report"]

    lines = [
        "# Churn Prediction Model — Evaluation Report",
        "",
        f"**Generated:** {metrics['trained_at']}",
        "",
        "---",
        "",
        "## 1. Model Configuration",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Algorithm | {model_info['algorithm']} |",
        f"| Number of Estimators | {model_info['n_estimators']} |",
        f"| Max Depth | {model_info['max_depth']} |",
        f"| Feature Scaler | {model_info['scaler']} |",
        f"| Number of Features | {model_info['n_features']} |",
        f"| Random State | {model_info['random_state']} |",
        "",
        "## 2. Dataset Summary",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| Original Rows | {ds['original_rows']:,} |",
        f"| Resampling | {ds['resampling_method']} |",
        f"| Resampled Rows | {ds['resampled_rows']:,} |",
        f"| Train Rows | {ds['train_rows']:,} |",
        f"| Test Rows | {ds['test_rows']:,} |",
        f"| Test Size | {ds['test_size'] * 100:.0f}% |",
        "",
        "## 3. Performance Metrics",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| **Train Accuracy** | {metrics['train_accuracy']:.4f} |",
        f"| **Test Accuracy** | {metrics['test_accuracy']:.4f} |",
        f"| **Precision** | {metrics['precision']:.4f} |",
        f"| **Recall** | {metrics['recall']:.4f} |",
        f"| **F1-Score** | {metrics['f1_score']:.4f} |",
        f"| **ROC-AUC** | {metrics['roc_auc']:.4f} |",
        "",
    ]

    # Embed metrics bar chart if generated
    if "metrics_bar" in plot_paths:
        lines += [
            f"![Performance Metrics]({plot_paths['metrics_bar'].name})",
            "",
        ]

    lines += [
        "## 4. Confusion Matrix",
        "",
        "|  | Predicted: Stay | Predicted: Churn |",
        "|---|---|---|",
        f"| **Actual: Stay** | {cm['true_negatives']:,} (TN) | {cm['false_positives']:,} (FP) |",
        f"| **Actual: Churn** | {cm['false_negatives']:,} (FN) | {cm['true_positives']:,} (TP) |",
        "",
        f"- **True Positives (correctly predicted churn):** {cm['true_positives']:,}",
        f"- **True Negatives (correctly predicted stay):** {cm['true_negatives']:,}",
        f"- **False Positives (incorrectly predicted churn):** {cm['false_positives']:,}",
        f"- **False Negatives (missed churn):** {cm['false_negatives']:,}",
        "",
    ]

    # Embed confusion matrix plot
    if "confusion_matrix" in plot_paths:
        lines += [
            f"![Confusion Matrix Heatmap]({plot_paths['confusion_matrix'].name})",
            "",
        ]

    lines += [
        "## 5. ROC Curve",
        "",
        f"AUC Score: **{metrics['roc_auc']:.4f}**",
        "",
    ]

    if "roc_curve" in plot_paths:
        lines += [
            f"![ROC Curve]({plot_paths['roc_curve'].name})",
            "",
        ]

    lines += [
        "## 6. Classification Report",
        "",
        "| Class | Precision | Recall | F1-Score | Support |",
        "|---|---|---|---|---|",
    ]

    for cls_key in ["0", "1"]:
        if cls_key in cls_rpt:
            c = cls_rpt[cls_key]
            label = "Stay (0)" if cls_key == "0" else "Churn (1)"
            lines.append(
                f"| {label} | {c['precision']:.4f} | {c['recall']:.4f} "
                f"| {c['f1-score']:.4f} | {int(c['support']):,} |"
            )

    if "macro avg" in cls_rpt:
        m = cls_rpt["macro avg"]
        lines.append(
            f"| **Macro Avg** | {m['precision']:.4f} | {m['recall']:.4f} "
            f"| {m['f1-score']:.4f} | {int(m['support']):,} |"
        )

    if "weighted avg" in cls_rpt:
        w = cls_rpt["weighted avg"]
        lines.append(
            f"| **Weighted Avg** | {w['precision']:.4f} | {w['recall']:.4f} "
            f"| {w['f1-score']:.4f} | {int(w['support']):,} |"
        )

    lines += [
        "",
        "## 7. Feature Importance",
        "",
    ]

    if "feature_importance" in plot_paths:
        lines += [
            f"![Feature Importance]({plot_paths['feature_importance'].name})",
            "",
        ]

    lines += [
        "| Rank | Feature | Importance |",
        "|---|---|---|",
    ]
    for i, fi in enumerate(feat_imp[:10], 1):
        bar = "\u2588" * int(fi["importance"] * 40)
        lines.append(f"| {i} | {fi['feature']} | {fi['importance']:.4f} {bar} |")

    lines += [
        "",
        "## 8. All Features Used",
        "",
        "```",
        ", ".join(model_info["features"]),
        "```",
        "",
        "---",
        "",
        "*Report generated by `src.ml.predict_churn` pipeline.*",
        "",
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  Evaluation JSON  : {json_path}")
    print(f"  Evaluation Report: {md_path}")
    if plot_paths:
        print(f"  Plots saved      : {len(plot_paths)} images in {REPORTS_DIR}")

    return json_path, md_path


def generate_evaluation_plots(metrics: dict, eval_data: dict) -> dict:
    """
    Generate evaluation plots and save as PNG files.
    Returns dict of {name: Path} for each generated plot.
    """
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from sklearn.metrics import roc_curve as sk_roc_curve

    plot_paths = {}
    colors = ["#4F46E5", "#10B981", "#F43F5E", "#F59E0B", "#06B6D4"]

    y_test = eval_data["y_test"]
    y_test_pred = eval_data["y_test_pred"]
    y_test_proba = eval_data["y_test_proba"]
    feat_imp = metrics["feature_importance"]
    cm = metrics["confusion_matrix"]

    # ── 1. Confusion Matrix Heatmap ──────────────────────────
    fig, ax = plt.subplots(figsize=(7, 5.5))
    cm_array = np.array([
        [cm["true_negatives"], cm["false_positives"]],
        [cm["false_negatives"], cm["true_positives"]],
    ])
    im = ax.imshow(cm_array, cmap="Blues", aspect="auto")
    plt.colorbar(im, ax=ax, shrink=0.8)

    labels = ["Stay (0)", "Churn (1)"]
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("Predicted Label", fontsize=12, fontweight="bold")
    ax.set_ylabel("Actual Label", fontsize=12, fontweight="bold")
    ax.set_title("Confusion Matrix", fontsize=14, fontweight="bold", pad=15)

    # Annotate cells
    for i in range(2):
        for j in range(2):
            val = cm_array[i, j]
            text_color = "white" if val > cm_array.max() / 2 else "black"
            label_map = [["TN", "FP"], ["FN", "TP"]]
            ax.text(j, i, f"{val:,}\n({label_map[i][j]})",
                    ha="center", va="center", fontsize=14,
                    fontweight="bold", color=text_color)

    fig.tight_layout()
    path = REPORTS_DIR / "confusion_matrix.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    plot_paths["confusion_matrix"] = path

    # ── 2. ROC Curve ─────────────────────────────────────────
    fpr, tpr, _ = sk_roc_curve(y_test, y_test_proba)
    auc_val = metrics["roc_auc"]

    fig, ax = plt.subplots(figsize=(7, 5.5))
    ax.plot(fpr, tpr, color=colors[0], lw=2.5,
            label=f"ROC Curve (AUC = {auc_val:.4f})")
    ax.plot([0, 1], [0, 1], color="#94A3B8", lw=1.5, linestyle="--",
            label="Random Classifier")
    ax.fill_between(fpr, tpr, alpha=0.12, color=colors[0])
    ax.set_xlabel("False Positive Rate", fontsize=12, fontweight="bold")
    ax.set_ylabel("True Positive Rate", fontsize=12, fontweight="bold")
    ax.set_title("ROC Curve", fontsize=14, fontweight="bold", pad=15)
    ax.legend(loc="lower right", fontsize=10)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1.02])
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    path = REPORTS_DIR / "roc_curve.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    plot_paths["roc_curve"] = path

    # ── 3. Feature Importance Bar Chart ───────────────────────
    top_n = min(15, len(feat_imp))
    top_features = feat_imp[:top_n]
    names = [f["feature"] for f in reversed(top_features)]
    values = [f["importance"] for f in reversed(top_features)]

    fig, ax = plt.subplots(figsize=(8, max(5, top_n * 0.4)))
    bars = ax.barh(names, values, color=colors[0], edgecolor="white", height=0.6)

    # Value labels on bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.003, bar.get_y() + bar.get_height() / 2,
                f"{val:.4f}", va="center", fontsize=9, color="#475569")

    ax.set_xlabel("Importance", fontsize=12, fontweight="bold")
    ax.set_title("Feature Importance (Random Forest)", fontsize=14,
                 fontweight="bold", pad=15)
    ax.grid(True, axis="x", alpha=0.3)
    ax.set_xlim(0, max(values) * 1.15)

    fig.tight_layout()
    path = REPORTS_DIR / "feature_importance.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    plot_paths["feature_importance"] = path

    # ── 4. Metrics Comparison Bar Chart ───────────────────────
    metric_names = ["Accuracy\n(Train)", "Accuracy\n(Test)", "Precision",
                    "Recall", "F1-Score", "ROC-AUC"]
    metric_vals = [
        metrics["train_accuracy"], metrics["test_accuracy"],
        metrics["precision"], metrics["recall"],
        metrics["f1_score"], metrics["roc_auc"],
    ]
    bar_colors = [colors[4], colors[0], colors[1], colors[3], colors[2], colors[0]]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(metric_names, metric_vals, color=bar_colors,
                  edgecolor="white", width=0.55)

    for bar, val in zip(bars, metric_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.008,
                f"{val:.4f}", ha="center", va="bottom", fontsize=10,
                fontweight="bold", color="#1E293B")

    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Score", fontsize=12, fontweight="bold")
    ax.set_title("Model Performance Metrics", fontsize=14,
                 fontweight="bold", pad=15)
    ax.grid(True, axis="y", alpha=0.3)
    ax.axhline(y=0.5, color="#CBD5E1", linestyle="--", lw=1)

    fig.tight_layout()
    path = REPORTS_DIR / "metrics_bar.png"
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    plot_paths["metrics_bar"] = path

    print(f"  Generated {len(plot_paths)} evaluation plots")
    return plot_paths


# ════════════════════════════════════════════════════════════
# 4. PREDICT FOR ALL CUSTOMERS
# ════════════════════════════════════════════════════════════

def predict_all(
    df: pd.DataFrame,
    model,
    scaler,
    encoders: dict,
    feature_cols: list,
) -> pd.DataFrame:
    """
    Run predictions for every row in the Silver data and return a
    DataFrame with columns:
        customerid, churn_probability, churn_prediction, risk_segment, prediction_time
    """
    work = df.copy()

    # ── Re-apply same categorical encoding ───────────────────
    if "preferedordercat" in work.columns:
        work.loc[work["preferedordercat"] == "Mobile", "preferedordercat"] = "Mobile Phone"
    if "preferredpaymentmode" in work.columns:
        work.loc[work["preferredpaymentmode"] == "COD", "preferredpaymentmode"] = "Cash on Delivery"
        work.loc[work["preferredpaymentmode"] == "CC", "preferredpaymentmode"] = "Credit Card"

    for col, le in encoders.items():
        if col in work.columns:
            # Handle unseen categories → assign -1, then clip to known range
            work[f"{col}_encoded"] = work[col].astype(str).apply(
                lambda x: le.transform([x])[0] if x in le.classes_ else -1
            )

    X_pred = work[feature_cols].copy()
    for col in X_pred.columns:
        if X_pred[col].isna().any():
            X_pred[col] = X_pred[col].fillna(X_pred[col].median())

    X_scaled = scaler.transform(X_pred)

    # ── Probabilities & predictions ──────────────────────────
    probas = model.predict_proba(X_scaled)[:, 1]  # P(churn=1)
    predictions = model.predict(X_scaled)

    # ── Risk segmentation ────────────────────────────────────
    def _risk_segment(p):
        if p > 0.75:
            return "High Risk"
        elif p >= 0.50:
            return "Medium Risk"
        return "Low Risk"

    now = datetime.now()

    result = pd.DataFrame({
        "customerid": work["customerid"].values,
        "churn_probability": np.round(probas, 4),
        "churn_prediction": predictions.astype(int),
        "risk_segment": [_risk_segment(p) for p in probas],
        "prediction_time": now,
    })

    # De-duplicate — keep the latest per customer
    result = result.drop_duplicates(subset="customerid", keep="last")

    print(f"  🔮  Predictions generated for {len(result):,} customers")
    high = (result["risk_segment"] == "High Risk").sum()
    med = (result["risk_segment"] == "Medium Risk").sum()
    low = (result["risk_segment"] == "Low Risk").sum()
    print(f"      High Risk: {high}  |  Medium Risk: {med}  |  Low Risk: {low}")

    return result


# ════════════════════════════════════════════════════════════
# 5. STORE PREDICTIONS IN GOLD
# ════════════════════════════════════════════════════════════

def create_predictions_table(engine) -> None:
    """Create gold.churn_predictions table if it doesn't exist."""
    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {GOLD_SCHEMA}.churn_predictions (
                customerid          VARCHAR PRIMARY KEY,
                churn_probability   FLOAT,
                churn_prediction    INTEGER,
                risk_segment        VARCHAR(20),
                prediction_time     TIMESTAMPTZ DEFAULT NOW()
            );
        """))
        conn.execute(text(f"""
            CREATE INDEX IF NOT EXISTS idx_churn_pred_risk
                ON {GOLD_SCHEMA}.churn_predictions (risk_segment);
        """))


def store_predictions(engine, predictions_df: pd.DataFrame) -> None:
    """Write predictions to gold.churn_predictions (full replace)."""
    create_predictions_table(engine)

    with engine.begin() as conn:
        predictions_df.to_sql(
            "churn_predictions",
            con=conn,
            schema=GOLD_SCHEMA,
            if_exists="replace",
            index=False,
        )
    print(f"  💾  Stored {len(predictions_df):,} predictions in {GOLD_SCHEMA}.churn_predictions")


def log_audit(engine, run_id: str, input_rows: int, output_rows: int, error: str = None):
    """Write an audit log entry for this prediction run."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO {BRONZE_SCHEMA}.etl_audit_log "
                    "(run_id, stage, input_rows, output_rows, error_summary) "
                    "VALUES (:run_id, :stage, :input_rows, :output_rows, :error_summary)"
                ),
                {
                    "run_id": run_id,
                    "stage": "churn_prediction",
                    "input_rows": int(input_rows),
                    "output_rows": int(output_rows),
                    "error_summary": error,
                },
            )
    except Exception:
        pass  # Don't fail pipeline if audit logging fails


# ════════════════════════════════════════════════════════════
# 6. MAIN PIPELINE
# ════════════════════════════════════════════════════════════

def run_pipeline(retrain: bool = True) -> None:
    """
    Full ML pipeline:
        1. Load from Silver
        2. Train model (or load saved)
        3. Predict for all customers
        4. Store to gold.churn_predictions
    """
    run_id = f"churn_predict_{uuid.uuid4()}"
    print("═" * 55)
    print("  🛡️  CHURN PREDICTION PIPELINE")
    print("═" * 55)

    engine = get_engine()
    ensure_schemas(engine)

    # ── 1. Load Silver data ──────────────────────────────────
    print("\n📦  Step 1: Loading Silver data...")
    silver_df = load_silver_data(engine)
    input_rows = len(silver_df)

    error_summary = None
    output_rows = 0

    try:
        # ── 2. Prepare features ──────────────────────────────
        print("\n🔧  Step 2: Preparing features...")
        X, y, encoders, feature_cols = prepare_features(silver_df)

        # ── 3. Train or load model ───────────────────────────
        if retrain or not MODEL_PATH.exists():
            print("\n  Step 3: Training Random Forest model...")
            model, scaler, metrics = train_model(X, y, feature_cols)

            # Get eval data for plots
            try:
                from imblearn.combine import SMOTETomek
                smt = SMOTETomek(random_state=42)
                X_res, y_res = smt.fit_resample(X, y)
            except ImportError:
                X_res, y_res = X, y
            X_train, X_test, y_train, y_test = train_test_split(
                X_res, y_res, test_size=0.30, random_state=42
            )
            eval_data = _get_eval_data(model, scaler, X_train, X_test, y_train, y_test)

            # Save model + metadata
            joblib.dump(
                {
                    "model": model,
                    "scaler": scaler,
                    "encoders": encoders,
                    "feature_cols": feature_cols,
                },
                MODEL_PATH,
            )
            print(f"  Model saved to {MODEL_PATH}")

            # Save evaluation report with plots
            print("\n  Step 3b: Saving evaluation report...")
            save_evaluation_report(metrics, eval_data)
        else:
            print("\n📂  Step 3: Loading saved model...")
            saved = joblib.load(MODEL_PATH)
            model = saved["model"]
            scaler = saved["scaler"]
            encoders = saved["encoders"]
            feature_cols = saved["feature_cols"]
            print(f"  ✅  Model loaded from {MODEL_PATH}")

        # ── 4. Predict ───────────────────────────────────────
        print("\n🔮  Step 4: Generating predictions...")
        predictions = predict_all(silver_df, model, scaler, encoders, feature_cols)
        output_rows = len(predictions)

        # ── 5. Store in Gold ─────────────────────────────────
        print("\n💾  Step 5: Storing predictions in Gold schema...")
        store_predictions(engine, predictions)

    except Exception as exc:
        error_summary = str(exc)
        print(f"\n  ❌  Pipeline failed: {error_summary}")
        raise

    finally:
        log_audit(engine, run_id, input_rows, output_rows, error_summary)
        engine.dispose()

    print("\n" + "═" * 55)
    print("  ✅  PIPELINE COMPLETE")
    print("═" * 55)


# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Churn Prediction Pipeline")
    parser.add_argument(
        "--predict",
        action="store_true",
        help="Predict only (load saved model, skip retraining)",
    )
    args = parser.parse_args()

    run_pipeline(retrain=not args.predict)

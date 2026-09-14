"""
Trains the optional logistic-regression secondary signal on a synthetic
labeled dataset and saves it to app/model.pkl, along with a held-out
evaluation report at app/model_metrics.json (surfaced on the dashboard).

This is a portfolio-project stand-in for real historical claims data: we
don't have any, so we generate feature vectors in the same shape the app
uses (see app/features.py) and assign a synthetic fraud label from a
weighted combination of those features plus noise. The model itself is
deliberately simple (logistic regression, six features) so its coefficients
can be read out and sanity-checked -- it's a second opinion, not a black
box.

Evaluation follows standard practice: a train/test split so metrics reflect
held-out performance, not memorization, plus precision/recall/F1 and ROC-AUC
rather than accuracy alone -- accuracy is a misleading headline metric here
because the synthetic label is intentionally imbalanced (fraud is rare),
same as real claims data.

Run with: python tools/train_model.py
"""
import json
import os
import sys

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, accuracy_score,
)
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.features import FEATURE_NAMES  # noqa: E402
from app.synthetic_data import generate_synthetic_dataset  # noqa: E402

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")


def main():
    X, y = generate_synthetic_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y,
    )

    model = LogisticRegression()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

    metrics = {
        "n_train": len(y_train),
        "n_test": len(y_test),
        "test_label_prevalence": round(float(y_test.mean()), 4),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "confusion_matrix": {
            "true_negative": int(tn), "false_positive": int(fp),
            "false_negative": int(fn), "true_positive": int(tp),
        },
        "coefficients": {name: round(float(c), 4) for name, c in zip(FEATURE_NAMES, model.coef_[0])},
        "intercept": round(float(model.intercept_[0]), 4),
    }

    print("Held-out test set evaluation (25% split, stratified):")
    print(f"  accuracy={metrics['accuracy']}  precision={metrics['precision']}  "
          f"recall={metrics['recall']}  f1={metrics['f1']}  roc_auc={metrics['roc_auc']}")
    print(f"  confusion matrix: TN={tn} FP={fp} FN={fn} TP={tp}")
    print("Coefficients (fit on the training split only):")
    for name, coef in metrics["coefficients"].items():
        print(f"  {name:28s} {coef:+.4f}")

    # Refit on the full dataset for the model that actually ships -- the
    # train/test split above exists purely to produce an honest metrics
    # report, not to hold back data from the final artifact.
    final_model = LogisticRegression()
    final_model.fit(X, y)
    joblib.dump(final_model, os.path.join(APP_DIR, "model.pkl"))

    with open(os.path.join(APP_DIR, "model_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nSaved model to app/model.pkl and evaluation report to app/model_metrics.json")


if __name__ == "__main__":
    main()

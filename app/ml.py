"""
Optional secondary risk signal: a scikit-learn logistic regression trained
on a synthetic labeled dataset (see tools/train_model.py).

This is explicitly a *second opinion*, not the decision-maker. The rules
engine in triage.py stands on its own and drives every routing decision;
this score is only ever displayed alongside it so an adjuster can see
whether a statistical model trained on the same features agrees.

If no trained model file exists, score_with_model returns None and the UI
simply omits the ML column -- nothing depends on this being present.
"""
import os

from app.features import feature_vector

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")

_model = None
_model_load_attempted = False


def _get_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    if os.path.exists(MODEL_PATH):
        import joblib
        _model = joblib.load(MODEL_PATH)
    return _model


def score_with_model(claim, policy):
    model = _get_model()
    if model is None:
        return None
    vector = [feature_vector(claim, policy)]
    probability_fraudulent = model.predict_proba(vector)[0][1]
    return round(float(probability_fraudulent), 3)

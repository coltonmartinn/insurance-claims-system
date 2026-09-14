"""
Synthetic labeled dataset generator for the optional ML secondary signal.

Shared by tools/train_model.py (which fits and ships app/model.pkl) and
notebooks/model_exploration.ipynb (which explores the same data in more
depth), so both start from the exact same generating process instead of
two copies drifting apart.
"""
import numpy as np

DEFAULT_SEED = 42
DEFAULT_N_SAMPLES = 4000


def generate_synthetic_dataset(n=DEFAULT_N_SAMPLES, seed=DEFAULT_SEED):
    """Returns (X, y): a feature matrix in the same six-column shape as
    app.features.FEATURE_NAMES, and a binary fraud label. There is no real
    labeled claims data available for a portfolio project, so labels come
    from a hand-picked weighted combination of the features plus noise,
    echoing the same intuitions as the rules engine in app/triage.py."""
    rng = np.random.default_rng(seed)

    amount_to_limit_ratio = rng.beta(2, 5, n)  # skewed low, occasional high
    policy_incident_gap_days = rng.exponential(200, n).clip(0, 3650)
    prior_claims_count = rng.poisson(0.6, n).clip(0, 8)
    is_round_number = rng.binomial(1, 0.15, n).astype(float)
    type_mismatch = rng.binomial(1, 0.08, n).astype(float)
    reporting_delay_days = rng.exponential(10, n).clip(0, 200)

    X = np.column_stack([
        amount_to_limit_ratio,
        policy_incident_gap_days,
        prior_claims_count,
        is_round_number,
        type_mismatch,
        reporting_delay_days,
    ])

    logit = (
        3.0 * amount_to_limit_ratio
        - 0.010 * policy_incident_gap_days  # gap shrinks risk as it grows
        + 0.35 * prior_claims_count
        + 0.8 * is_round_number
        + 1.4 * type_mismatch
        + 0.015 * reporting_delay_days
        - 2.5  # intercept so baseline risk is low
    )
    noise = rng.normal(0, 1.0, n)
    probability = 1 / (1 + np.exp(-(logit + noise)))
    labels = rng.binomial(1, probability)

    return X, labels


def rules_score_from_features(X):
    """Reproduces app.triage's point-scoring logic directly from the six
    normalized features (in app.features.FEATURE_NAMES order), so the
    rules engine and the ML model can be scored on the exact same rows for
    a direct, apples-to-apples comparison. Kept here rather than calling
    triage.py directly because those rules operate on ORM Claim/Policy
    objects with raw dates and dollar amounts, not normalized features --
    this is the same arithmetic, translated to work on a feature matrix."""
    amount_ratio = X[:, 0]
    gap_days = X[:, 1]
    prior_claims = X[:, 2]
    is_round = X[:, 3]
    mismatch = X[:, 4]
    delay_days = X[:, 5]

    score = np.zeros(len(X))
    score += np.where(amount_ratio >= 0.8, 30, np.where(amount_ratio >= 0.5, 15, 0))
    score += np.where(gap_days <= 14, 25, np.where(gap_days <= 30, 10, 0))
    score += np.where(prior_claims >= 3, 20, np.where(prior_claims >= 1, 10, 0))
    score += np.where(is_round >= 1, 10, 0)
    score += np.where(mismatch >= 1, 20, 0)
    score += np.where(delay_days > 60, 15, np.where(delay_days > 30, 5, 0))
    return score

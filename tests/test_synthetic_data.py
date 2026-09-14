"""Unit tests for the synthetic dataset generator and the rules-score
reproduction used to compare the rules engine against the ML model."""
import numpy as np

from app.synthetic_data import generate_synthetic_dataset, rules_score_from_features


def test_generate_synthetic_dataset_is_deterministic_for_same_seed():
    X1, y1 = generate_synthetic_dataset(n=200, seed=7)
    X2, y2 = generate_synthetic_dataset(n=200, seed=7)
    assert np.array_equal(X1, X2)
    assert np.array_equal(y1, y2)


def test_generate_synthetic_dataset_shape_and_label_range():
    X, y = generate_synthetic_dataset(n=500, seed=1)
    assert X.shape == (500, 6)
    assert set(np.unique(y)).issubset({0, 1})


def test_rules_score_matches_amount_ratio_thresholds():
    X = np.array([
        [0.9, 400, 0, 0, 0, 0],   # ratio >= 0.8 -> 30
        [0.6, 400, 0, 0, 0, 0],   # ratio >= 0.5 -> 15
        [0.1, 400, 0, 0, 0, 0],   # below threshold -> 0
    ])
    scores = rules_score_from_features(X)
    assert list(scores) == [30, 15, 0]


def test_rules_score_stacks_multiple_fired_rules():
    # High ratio (30) + short gap (25) + prior claims (20) + round number
    # (10) + mismatch (20) + late reporting (15) = 120
    X = np.array([[0.9, 5, 3, 1, 1, 70]])
    assert rules_score_from_features(X)[0] == 120


def test_rules_score_zero_for_clean_row():
    X = np.array([[0.1, 400, 0, 0, 0, 5]])
    assert rules_score_from_features(X)[0] == 0

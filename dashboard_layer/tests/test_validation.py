import numpy as np
import pytest
from dashboard_layer.utils.validation import (
    cohens_d,
    fdr_correction,
    run_hypothesis_test,
    calculate_classification_metrics,
)


def test_cohens_d_known_value():
    """Test Cohen's d with a known effect size."""
    # group1: mean=1, std=1
    group1 = np.array([0, 1, 2])
    # group2: mean=3, std=1
    group2 = np.array([2, 3, 4])

    # n1=3, n2=3, var1=1, var2=1
    # pooled_std = sqrt(((2*1 + 2*1)/(3+3-2))) = sqrt(4/4) = 1
    # cohens_d = (1 - 3) / 1 = -2.0
    d = cohens_d(group1, group2)

    assert d == pytest.approx(-2.0)


def test_cohens_d_zero_std():
    """Test Cohen's d when the pooled standard deviation is zero."""
    group1 = np.array([1, 1, 1, 1, 1])
    group2 = np.array([2, 2, 2, 2, 2])

    # The function should handle this gracefully by returning 0.0
    d = cohens_d(group1, group2)
    assert d == 0.0

def test_fdr_correction_bh():
    """Test the Benjamini-Hochberg FDR correction."""
    p_values = [0.01, 0.02, 0.03, 0.04, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
    n = len(p_values)

    # Expected corrected p-values (p * n / rank)
    # [0.01*10/1, 0.02*10/2, 0.03*10/3, ..., 0.5*10/10]
    # [0.1, 0.1, 0.1, 0.1, 0.1, 0.166, 0.285, 0.375, 0.444, 0.5]
    # After enforcing montonicity, the first 6 values should be 0.1
    expected_corrected = [
        0.1, 0.1, 0.1, 0.1, 0.1, 0.16666667, 0.28571429,
        0.375, 0.44444444, 0.5
    ]
    expected_significant = [True, True, True, True, True, False, False, False, False, False]

    corrected, significant = fdr_correction(p_values, alpha=0.15)

    assert corrected == pytest.approx(expected_corrected, abs=1e-2)
    assert significant == expected_significant

def test_run_hypothesis_test_directional():
    """Test the directional hypothesis test wrapper."""
    depressed = np.array([1, 2, 3, 4, 5])  # mean=3
    nondepressed = np.array([4, 5, 6, 7, 8])  # mean=6

    # Test case 1: depressed < nondepressed (correct direction)
    result1 = run_hypothesis_test("test_feature", depressed, nondepressed, expected_direction="<")

    assert result1.feature == "test_feature"
    assert result1.direction_correct is True
    assert result1.p_value < 0.05
    assert result1.depressed_mean == 3
    assert result1.nondepressed_mean == 6

    # Test case 2: depressed > nondepressed (incorrect direction)
    result2 = run_hypothesis_test("test_feature", depressed, nondepressed, expected_direction=">")

    assert result2.direction_correct is False
    assert result2.p_value > 0.95

def test_calculate_classification_metrics_basic():
    """Test the calculation of classification metrics."""
    y_true = np.array([1, 1, 0, 0, 1, 0])
    y_pred = np.array([1, 0, 0, 1, 1, 0])

    # TP=2, TN=2, FP=1, FN=1
    metrics = calculate_classification_metrics(y_true, y_pred)

    assert metrics.tp == 2
    assert metrics.tn == 2
    assert metrics.fp == 1
    assert metrics.fn == 1

    assert metrics.sensitivity == pytest.approx(2/3)
    assert metrics.specificity == pytest.approx(2/3)
    assert metrics.ppv == pytest.approx(2/3)
    assert metrics.npv == pytest.approx(2/3)

    assert metrics.accuracy == pytest.approx(4/6)
    assert metrics.f1_score == pytest.approx(2 * ( (2/3)*(2/3) ) / (2/3 + 2/3) )

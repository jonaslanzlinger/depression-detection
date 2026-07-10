"""
Research Validation Utilities.

Statistical functions for validating the depression detection system
against ground truth data (DAIC-WOZ dataset with PHQ-8 scores).
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class HypothesisResult:
    """Result of a single hypothesis test."""
    feature: str
    direction: str  # "<" or ">"
    depressed_mean: float
    depressed_std: float
    nondepressed_mean: float
    nondepressed_std: float
    cohens_d: float
    cohens_d_ci: Tuple[float, float]
    u_statistic: float
    p_value: float
    p_value_corrected: Optional[float]
    significant: bool
    direction_correct: bool
    n_depressed: int
    n_nondepressed: int


@dataclass
class ClassificationMetrics:
    """Classification performance metrics."""
    sensitivity: float  # True Positive Rate (Recall)
    specificity: float  # True Negative Rate
    ppv: float  # Positive Predictive Value (Precision)
    npv: float  # Negative Predictive Value
    accuracy: float
    f1_score: float
    auc_roc: Optional[float]
    threshold: float
    tp: int
    tn: int
    fp: int
    fn: int


def load_evaluation_dataset(csv_path: str) -> pd.DataFrame:
    """
    Load the evaluation dataset CSV with participant-level data.

    Expected columns: participant_id, gender, PHQ-8 items, acoustic features
    """
    df = pd.read_csv(csv_path)

    # Calculate depression status based on PHQ-8 total score
    phq8_cols = [col for col in df.columns if col.startswith('PHQ8_')]
    if phq8_cols:
        df['phq8_total'] = df[phq8_cols].sum(axis=1)
        df['is_depressed'] = df['phq8_total'] >= 10  # Clinical cutoff

    return df


def load_cohort_data(depressed_path: str, nondepressed_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load the cohort JSON files with aggregated metrics.

    The JSON files contain records in long format (time-series per metric):
    [{"user_id": 1, "timestamp": "...", "metric_name": "f0_avg", "metric_value": 198.2}, ...]

    This function pivots them to wide format for analysis, where each time point
    becomes a sample:
    DataFrame with columns: timestamp, f0_avg, f0_std, ...

    Returns:
        Tuple of (depressed_df, nondepressed_df)
    """
    with open(depressed_path, 'r') as f:
        depressed_data = json.load(f)

    with open(nondepressed_path, 'r') as f:
        nondepressed_data = json.load(f)

    def pivot_long_to_wide(data: List[Dict]) -> pd.DataFrame:
        """Convert long format metrics to wide format DataFrame."""
        df = pd.DataFrame(data)

        # Check if data is already in wide format
        if 'metric_name' not in df.columns:
            return df

        # For time-series data, we need to pivot using timestamp as the index
        # Each timestamp becomes a sample (row)
        if 'timestamp' in df.columns:
            # Preserve user-level columns like 'gender' during pivot
            index_cols = ['timestamp']
            if 'gender' in df.columns:
                index_cols.append('gender')

            # Pivot from long to wide format
            pivot_df = df.pivot_table(
                index=index_cols,
                columns='metric_name',
                values='metric_value',
                aggfunc='first'  # Take first value if duplicates
            ).reset_index()
        else:
            # Fallback: create a synthetic index for each metric observation
            # Group by metric_name and assign row numbers
            df['sample_id'] = df.groupby('metric_name').cumcount()
            pivot_df = df.pivot_table(
                index='sample_id',
                columns='metric_name',
                values='metric_value',
                aggfunc='first'
            ).reset_index()

        # Flatten column names
        pivot_df.columns.name = None

        return pivot_df

    depressed_df = pivot_long_to_wide(depressed_data)
    nondepressed_df = pivot_long_to_wide(nondepressed_data)

    return depressed_df, nondepressed_df


def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """
    Calculate Cohen's d effect size.

    Uses pooled standard deviation for independent samples.
    """
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

    if pooled_std == 0:
        return 0.0

    return (np.mean(group1) - np.mean(group2)) / pooled_std


def cohens_d_ci(group1: np.ndarray, group2: np.ndarray, n_boot: int = 1000, ci: float = 0.95) -> Tuple[float, Tuple[float, float]]:
    """
    Calculate Cohen's d with bootstrap confidence interval.
    """
    # Calculate observed Cohen's d
    d_observed = cohens_d(group1, group2)

    # Bootstrap resampling
    boot_d = []
    if len(group1) > 1 and len(group2) > 1:
        for _ in range(n_boot):
            g1_sample = np.random.choice(group1, size=len(group1), replace=True)
            g2_sample = np.random.choice(group2, size=len(group2), replace=True)
            boot_d.append(cohens_d(g1_sample, g2_sample))

    if boot_d:
        # Calculate confidence interval
        lower_bound = np.percentile(boot_d, (1 - ci) / 2 * 100)
        upper_bound = np.percentile(boot_d, (1 + ci) / 2 * 100)
        return d_observed, (lower_bound, upper_bound)
    else:
        return d_observed, (np.nan, np.nan)


def interpret_cohens_d(d: float) -> str:
    """Interpret Cohen's d effect size magnitude."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def effect_size_change_ci(
    depressed_df: pd.DataFrame,
    nondepressed_df: pd.DataFrame,
    feature: str,
    n_boot: int = 1000,
    ci: float = 0.95
) -> Tuple[float, Tuple[float, float]]:
    """
    Calculate the confidence interval for the change in effect size after stratification.
    """
    boot_diffs = []

    for _ in range(n_boot):
        # Resample with replacement
        dep_sample = depressed_df.sample(n=len(depressed_df), replace=True)
        nondep_sample = nondepressed_df.sample(n=len(nondepressed_df), replace=True)

        # 1. Unadjusted effect size
        agg_dep = dep_sample[feature].dropna()
        agg_nondep = nondep_sample[feature].dropna()
        if len(agg_dep) < 2 or len(agg_nondep) < 2:
            continue
        d_unadjusted = cohens_d(agg_dep.values, agg_nondep.values)

        # 2. Adjusted effect size
        gender_effects = []
        for gender in ['female', 'male']:
            dep_gender = dep_sample[dep_sample['gender'] == gender][feature].dropna()
            nondep_gender = nondep_sample[nondep_sample['gender'] == gender][feature].dropna()

            if len(dep_gender) > 1 and len(nondep_gender) > 1:
                gender_effects.append(cohens_d(dep_gender.values, nondep_gender.values))

        if not gender_effects:
            continue
        d_adjusted = np.mean(gender_effects)

        # 3. Difference
        boot_diffs.append(d_unadjusted - d_adjusted)

    if boot_diffs:
        # Observed difference
        obs_unadjusted = cohens_d(depressed_df[feature].dropna().values, nondepressed_df[feature].dropna().values)
        obs_gender_effects = [
            cohens_d(
                depressed_df[depressed_df['gender'] == g][feature].dropna().values,
                nondepressed_df[nondepressed_df['gender'] == g][feature].dropna().values
            )
            for g in ['female', 'male'] if not depressed_df[depressed_df['gender'] == g][feature].dropna().empty and not nondepressed_df[nondepressed_df['gender'] == g][feature].dropna().empty
        ]
        obs_adjusted = np.mean(obs_gender_effects) if obs_gender_effects else 0
        obs_diff = obs_unadjusted - obs_adjusted

        lower_bound = np.percentile(boot_diffs, (1 - ci) / 2 * 100)
        upper_bound = np.percentile(boot_diffs, (1 + ci) / 2 * 100)
        return obs_diff, (lower_bound, upper_bound)
    else:
        return np.nan, (np.nan, np.nan)


def mann_whitney_u_test(
    depressed: np.ndarray,
    nondepressed: np.ndarray,
    alternative: str = 'two-sided'
) -> Tuple[float, float]:
    """
    Perform Mann-Whitney U test.

    Args:
        depressed: Values from depressed group
        nondepressed: Values from non-depressed group
        alternative: 'two-sided', 'less', or 'greater'

    Returns:
        Tuple of (U statistic, p-value)
    """
    statistic, pvalue = stats.mannwhitneyu(
        depressed, nondepressed,
        alternative=alternative
    )
    return statistic, pvalue


def fdr_correction(p_values: List[float], alpha: float = 0.05) -> Tuple[List[float], List[bool]]:
    """
    Apply Benjamini-Hochberg FDR correction.

    Args:
        p_values: List of raw p-values
        alpha: Significance level (default 0.05)

    Returns:
        Tuple of (corrected p-values, significance boolean list)
    """
    n = len(p_values)
    if n == 0:
        return [], []

    # Sort p-values and keep track of original indices
    sorted_indices = np.argsort(p_values)
    sorted_pvals = np.array(p_values)[sorted_indices]

    # Calculate adjusted p-values
    adjusted = np.zeros(n)
    for i in range(n):
        rank = i + 1
        adjusted[sorted_indices[i]] = sorted_pvals[i] * n / rank

    # Ensure monotonicity (each adjusted p-value >= previous)
    adjusted_sorted = adjusted[sorted_indices]
    for i in range(n - 2, -1, -1):
        adjusted_sorted[i] = min(adjusted_sorted[i], adjusted_sorted[i + 1])

    # Put back in original order and cap at 1.0
    corrected = np.minimum(adjusted_sorted[np.argsort(sorted_indices)], 1.0)
    significant = corrected < alpha

    return corrected.tolist(), significant.tolist()


def run_hypothesis_test(
    feature: str,
    depressed_values: np.ndarray,
    nondepressed_values: np.ndarray,
    expected_direction: str
) -> HypothesisResult:
    """
    Run a single directional hypothesis test.

    Args:
        feature: Name of the feature being tested
        depressed_values: Array of values from depressed group
        nondepressed_values: Array of values from non-depressed group
        expected_direction: Expected direction ("<" or ">")
            "<" means depressed < nondepressed
            ">" means depressed > nondepressed

    Returns:
        HypothesisResult with test statistics
    """
    # Clean data (remove NaN/inf)
    dep_clean = depressed_values[np.isfinite(depressed_values)]
    nondep_clean = nondepressed_values[np.isfinite(nondepressed_values)]

    if len(dep_clean) < 3 or len(nondep_clean) < 3:
        return HypothesisResult(
            feature=feature,
            direction=expected_direction,
            depressed_mean=np.nan,
            depressed_std=np.nan,
            nondepressed_mean=np.nan,
            nondepressed_std=np.nan,
            cohens_d=np.nan,
            cohens_d_ci=(np.nan, np.nan),
            u_statistic=np.nan,
            p_value=1.0,
            p_value_corrected=None,
            significant=False,
            direction_correct=False,
            n_depressed=len(dep_clean),
            n_nondepressed=len(nondep_clean)
        )

    # Calculate descriptive statistics
    dep_mean = np.mean(dep_clean)
    dep_std = np.std(dep_clean, ddof=1)
    nondep_mean = np.mean(nondep_clean)
    nondep_std = np.std(nondep_clean, ddof=1)

    # Cohen's d with CI
    d, d_ci = cohens_d_ci(dep_clean, nondep_clean)

    # Determine actual direction
    actual_direction = "<" if dep_mean < nondep_mean else ">"
    direction_correct = actual_direction == expected_direction

    # Mann-Whitney U test (one-tailed based on expected direction)
    if expected_direction == "<":
        alternative = 'less'
    else:
        alternative = 'greater'

    u_stat, p_value = mann_whitney_u_test(dep_clean, nondep_clean, alternative)

    return HypothesisResult(
        feature=feature,
        direction=expected_direction,
        depressed_mean=dep_mean,
        depressed_std=dep_std,
        nondepressed_mean=nondep_mean,
        nondepressed_std=nondep_std,
        cohens_d=d,
        cohens_d_ci=d_ci,
        u_statistic=u_stat,
        p_value=p_value,
        p_value_corrected=None,  # Set later after FDR
        significant=False,  # Set later after FDR
        direction_correct=direction_correct,
        n_depressed=len(dep_clean),
        n_nondepressed=len(nondep_clean)
    )


def run_all_hypothesis_tests(
    depressed_df: pd.DataFrame,
    nondepressed_df: pd.DataFrame,
    hypotheses: List[Tuple[str, str]],
    alpha: float = 0.05
) -> List[HypothesisResult]:
    """
    Run all hypothesis tests with FDR correction.

    Args:
        depressed_df: DataFrame with depressed cohort data
        nondepressed_df: DataFrame with non-depressed cohort data
        hypotheses: List of (feature_name, expected_direction) tuples
        alpha: Significance level for FDR correction

    Returns:
        List of HypothesisResult objects with corrected p-values
    """
    results = []

    for feature, direction in hypotheses:
        if feature not in depressed_df.columns or feature not in nondepressed_df.columns:
            continue

        dep_values = depressed_df[feature].dropna().values
        nondep_values = nondepressed_df[feature].dropna().values

        result = run_hypothesis_test(feature, dep_values, nondep_values, direction)
        results.append(result)

    # Apply FDR correction
    if results:
        p_values = [r.p_value for r in results]
        corrected_pvals, significant = fdr_correction(p_values, alpha)

        for i, result in enumerate(results):
            result.p_value_corrected = corrected_pvals[i]
            result.significant = significant[i]

    return results


def calculate_classification_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None
) -> ClassificationMetrics:
    """
    Calculate classification performance metrics.

    Args:
        y_true: Ground truth binary labels (1=depressed, 0=not depressed)
        y_pred: Predicted binary labels
        y_prob: Optional predicted probabilities for AUC calculation

    Returns:
        ClassificationMetrics object
    """
    # Confusion matrix components
    tp = np.sum((y_true == 1) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))

    # Metrics
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    ppv = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    npv = tn / (tn + fn) if (tn + fn) > 0 else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0

    # F1 Score
    if ppv + sensitivity > 0:
        f1 = 2 * (ppv * sensitivity) / (ppv + sensitivity)
    else:
        f1 = 0.0

    # AUC-ROC (if probabilities provided)
    auc_roc = None
    if y_prob is not None and len(np.unique(y_true)) > 1:
        try:
            from sklearn.metrics import roc_auc_score
            auc_roc = roc_auc_score(y_true, y_prob)
        except ImportError:
            # Calculate manually using trapezoidal rule
            auc_roc = _calculate_auc_manual(y_true, y_prob)

    return ClassificationMetrics(
        sensitivity=sensitivity,
        specificity=specificity,
        ppv=ppv,
        npv=npv,
        accuracy=accuracy,
        f1_score=f1,
        auc_roc=auc_roc,
        threshold=0.5,
        tp=int(tp),
        tn=int(tn),
        fp=int(fp),
        fn=int(fn)
    )


def _calculate_auc_manual(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate AUC-ROC manually without sklearn."""
    # Sort by predicted probability
    sorted_indices = np.argsort(y_prob)[::-1]
    y_true_sorted = y_true[sorted_indices]

    # Count positives and negatives
    n_pos = np.sum(y_true == 1)
    n_neg = np.sum(y_true == 0)

    if n_pos == 0 or n_neg == 0:
        return 0.5

    # Calculate AUC using rank sum
    rank_sum = 0
    for i, label in enumerate(y_true_sorted):
        if label == 1:
            rank_sum += len(y_true) - i

    auc = (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
    return auc


def calculate_correlation_matrix(
    indicator_scores: Dict[str, List[float]],
    phq8_scores: Dict[str, List[float]]
) -> pd.DataFrame:
    """
    Calculate correlation matrix between indicator scores and PHQ-8 items.

    Args:
        indicator_scores: Dict mapping indicator names to score lists
        phq8_scores: Dict mapping PHQ-8 item names to score lists

    Returns:
        DataFrame with Spearman correlation coefficients
    """
    # Combine into DataFrames
    ind_df = pd.DataFrame(indicator_scores)
    phq_df = pd.DataFrame(phq8_scores)

    combined = pd.concat([ind_df, phq_df], axis=1)

    # Calculate Spearman correlations
    corr_matrix = combined.corr(method='spearman')

    # Return only the cross-correlations
    return corr_matrix.loc[indicator_scores.keys(), phq8_scores.keys()]


def calculate_indicator_phq8_mapping_accuracy(
    indicator_scores: pd.DataFrame,
    phq8_scores: pd.DataFrame,
    mapping: Dict[str, str]
) -> Dict[str, Dict[str, float]]:
    """
    Calculate how well each indicator maps to its corresponding PHQ-8 item.

    Args:
        indicator_scores: DataFrame with indicator scores per participant
        phq8_scores: DataFrame with PHQ-8 item scores per participant
        mapping: Dict mapping indicator names to PHQ-8 item names

    Returns:
        Dict with correlation and significance for each mapping
    """
    results = {}

    for indicator, phq_item in mapping.items():
        if indicator not in indicator_scores.columns:
            continue
        if phq_item not in phq8_scores.columns:
            continue

        ind_vals = indicator_scores[indicator].values
        phq_vals = phq8_scores[phq_item].values

        # Remove NaN pairs
        mask = ~(np.isnan(ind_vals) | np.isnan(phq_vals))
        ind_clean = ind_vals[mask]
        phq_clean = phq_vals[mask]

        if len(ind_clean) < 3:
            continue

        # Spearman correlation
        rho, p_value = stats.spearmanr(ind_clean, phq_clean)

        results[indicator] = {
            'phq8_item': phq_item,
            'correlation': rho,
            'p_value': p_value,
            'n_samples': len(ind_clean)
        }

    return results


# Default directional hypotheses based on depression research literature
# Format: (feature_name, expected_direction)
# "<" means depressed < nondepressed, ">" means depressed > nondepressed
DEFAULT_HYPOTHESES = [
    # Pitch (F0) - typically lower/less variable in depression
    ("f0_avg", "<"),
    ("f0_std", "<"),
    ("f0_range", "<"),

    # Speech rate - typically slower in depression
    ("rate_of_speech", "<"),
    ("articulation_rate", "<"),
    ("speaking_rate", "<"),

    # Pausing - typically longer/more frequent in depression
    ("pause_duration", ">"),
    ("pause_rate", ">"),
    ("pause_count", ">"),
    ("silence_ratio", ">"),

    # Energy/Intensity - typically lower/less dynamic in depression.
    # The pipeline produces rms_energy_* (not energy_*/intensity_*); without these the
    # energy markers were silently filtered out of validation even though the cohort
    # data contains them. The generic aliases below are kept (harmlessly filtered out
    # when absent) for datasets that use different names.
    ("rms_energy_mean", "<"),
    ("rms_energy_std", "<"),
    ("rms_energy_range", "<"),
    ("intensity_mean", "<"),
    ("intensity_std", "<"),
    ("energy_mean", "<"),
    ("energy_std", "<"),
    ("dynamic_range", "<"),

    # Jitter/Shimmer - typically higher in depression (voice quality)
    ("jitter", ">"),
    ("shimmer", ">"),
    ("jitter_local", ">"),
    ("shimmer_local", ">"),

    # HNR - typically lower in depression (breathier voice)
    ("hnr", "<"),
    ("hnr_mean", "<"),

    # Spectral features
    ("spectral_centroid", "<"),
    ("spectral_flux", "<"),
    ("mfcc_1_mean", "<"),
]


# PHQ-8 to DSM-5 Indicator Mapping
PHQ8_TO_INDICATOR_MAPPING = {
    "1_depressed_mood": "PHQ8_Depressed",
    "2_loss_of_interest": "PHQ8_NoInterest",
    "4_sleep_disturbance": "PHQ8_Sleep",
    "5_psychomotor_changes": "PHQ8_Tired",  # Closest match
    "6_fatigue": "PHQ8_Tired",
    "7_worthlessness": "PHQ8_BadSelf",
    "8_concentration_difficulties": "PHQ8_Concentrate",
    "9_suicidal_ideation": "PHQ8_BetterDead",
}

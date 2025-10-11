"""
RDM Comparison Script for Research Methods Paper
Compares two different data collection methods for measuring representational dissimilarity
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error

DEFAULT_SEED = 20240215
BOOTSTRAP_SAMPLES = 5000


def set_global_seeds(seed: int = DEFAULT_SEED) -> None:
    """Set all RNG seeds used by this module."""

    random.seed(seed)
    np.random.seed(seed)


def load_rdm(filepath):
    """Load RDM from CSV file - returns numpy array and labels.

    This uses pandas to robustly handle row/column labels. The CSV is expected
    to have a leading index column with row labels and matching column headers.
    """
    df = pd.read_csv(filepath, index_col=0)
    # Convert to numpy float matrix
    matrix = df.values.astype(float)
    labels = list(map(str, df.columns.tolist()))
    return matrix, labels

def rdm_to_dataframe(matrix, labels):
    """Convert RDM matrix and labels to DataFrame - for visualization only"""
    # Create dict for DataFrame
    data_dict = {}
    for i, label in enumerate(labels):
        data_dict[label] = matrix[:, i]
    
    # Create DataFrame from dict
    df = pd.DataFrame(data_dict)
    # Use simple integer index first
    df.index = labels
    return df

def get_lower_triangle(rdm_matrix):
    """Extract lower triangle of RDM (excluding diagonal) as 1D array"""
    # Get lower triangle indices (k=-1 excludes diagonal)
    lower_tri_indices = np.tril_indices_from(rdm_matrix, k=-1)
    return rdm_matrix[lower_tri_indices]


def safe_normalize(arr):
    """Normalize array or matrix to 0-1 safely, handling constant arrays."""
    arr = np.array(arr, dtype=float)
    mn = np.nanmin(arr)
    mx = np.nanmax(arr)
    rng = mx - mn
    if rng == 0 or np.isnan(rng):
        return np.zeros_like(arr)
    return (arr - mn) / rng

def concordance_correlation_coefficient(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Lin's concordance correlation coefficient for two vectors."""

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    cov_xy = np.cov(x, y, ddof=0)[0, 1]
    mean_x = np.mean(x)
    mean_y = np.mean(y)
    var_x = np.var(x, ddof=0)
    var_y = np.var(y, ddof=0)
    denom = var_x + var_y + (mean_x - mean_y) ** 2
    if denom == 0:
        return float("nan")
    return float(2 * cov_xy / denom)


def deming_regression(x: np.ndarray, y: np.ndarray, lambda_: float = 1.0) -> Tuple[float, float]:
    """Compute slope and intercept for Deming regression with ratio lambda_."""

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    s_xx = np.var(x, ddof=1)
    s_yy = np.var(y, ddof=1)
    s_xy = np.cov(x, y, ddof=1)[0, 1]

    term = s_yy - lambda_ * s_xx
    slope = (term + np.sqrt(term**2 + 4 * lambda_ * s_xy**2)) / (2 * s_xy)
    intercept = y_mean - slope * x_mean
    return float(slope), float(intercept)


def bootstrap_deming_ci(
    x: np.ndarray,
    y: np.ndarray,
    *,
    lambda_: float = 1.0,
    n_boot: int = BOOTSTRAP_SAMPLES,
    alpha: float = 0.05,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Return bootstrap confidence intervals for Deming slope and intercept."""

    if rng is None:
        rng = np.random.default_rng()

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    slopes = np.empty(n_boot, dtype=float)
    intercepts = np.empty(n_boot, dtype=float)

    for i in range(n_boot):
        idx = rng.integers(0, x.size, size=x.size)
        slopes[i], intercepts[i] = deming_regression(x[idx], y[idx], lambda_=lambda_)

    lower_q, upper_q = alpha / 2.0, 1.0 - alpha / 2.0
    slope_ci = (
        float(np.quantile(slopes, lower_q)),
        float(np.quantile(slopes, upper_q)),
    )
    intercept_ci = (
        float(np.quantile(intercepts, lower_q)),
        float(np.quantile(intercepts, upper_q)),
    )
    return slope_ci, intercept_ci


def bland_altman_stats(x: np.ndarray, y: np.ndarray) -> Tuple[float, Tuple[float, float]]:
    """Return Bland–Altman mean difference and limits of agreement (x - y)."""

    diff = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    mean_diff = float(np.mean(diff))
    std_diff = float(np.std(diff, ddof=1))
    loa = (mean_diff - 1.96 * std_diff, mean_diff + 1.96 * std_diff)
    return mean_diff, loa


def compare_rdms(
    rdm1_matrix,
    rdm2_matrix,
    method1_name="Method 1",
    method2_name="Method 2",
    *,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    rng: Optional[np.random.Generator] = None,
):
    """
    Compare two RDMs using multiple metrics
    
    Parameters:
    -----------
    rdm1_matrix, rdm2_matrix : numpy array
        The two RDM matrices to compare
    method1_name, method2_name : str
        Names of the methods for labeling
        
    Returns:
    --------
    dict : Dictionary containing comparison metrics
    """
    # Extract lower triangles
    rdm1_lower = get_lower_triangle(rdm1_matrix)
    rdm2_lower = get_lower_triangle(rdm2_matrix)
    
    # Calculate correlations
    pearson_r, pearson_p = pearsonr(rdm1_lower, rdm2_lower)
    spearman_r, spearman_p = spearmanr(rdm1_lower, rdm2_lower)
    
    # Calculate error metrics
    mse = mean_squared_error(rdm1_lower, rdm2_lower)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(rdm1_lower, rdm2_lower)
    
    # Calculate normalized metrics
    # Normalize both RDMs to 0-1 range for fair comparison
    rdm1_norm = (rdm1_lower - rdm1_lower.min()) / (rdm1_lower.max() - rdm1_lower.min())
    rdm2_norm = (rdm2_lower - rdm2_lower.min()) / (rdm2_lower.max() - rdm2_lower.min())
    
    mse_norm = mean_squared_error(rdm1_norm, rdm2_norm)
    rmse_norm = np.sqrt(mse_norm)
    mae_norm = mean_absolute_error(rdm1_norm, rdm2_norm)
    
    results = {
        'pearson_r': pearson_r,
        'pearson_p': pearson_p,
        'spearman_r': spearman_r,
        'spearman_p': spearman_p,
        'rmse': rmse,
        'mae': mae,
        'rmse_normalized': rmse_norm,
        'mae_normalized': mae_norm,
        'n_comparisons': len(rdm1_lower)
    }

    results['ccc'] = concordance_correlation_coefficient(rdm1_lower, rdm2_lower)

    slope, intercept = deming_regression(rdm1_lower, rdm2_lower)
    results['deming_slope'] = slope
    results['deming_intercept'] = intercept

    if bootstrap_samples and bootstrap_samples > 0:
        slope_ci, intercept_ci = bootstrap_deming_ci(
            rdm1_lower,
            rdm2_lower,
            n_boot=bootstrap_samples,
            rng=rng,
        )
        results['deming_slope_ci'] = slope_ci
        results['deming_intercept_ci'] = intercept_ci

    mean_diff, loa = bland_altman_stats(rdm1_lower, rdm2_lower)
    results['bland_altman_mean_diff'] = mean_diff
    results['bland_altman_loa'] = loa

    return results, rdm1_lower, rdm2_lower, rdm1_norm, rdm2_norm

def plot_rdm_comparison(rdm1_matrix, rdm2_matrix, subject_id, method1_name="Behavior", method2_name="Multi-arrangement"):
    """
    Create visualization comparing two RDMs
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # Plot RDM 1
    im1 = axes[0, 0].imshow(rdm1_matrix, cmap='viridis', aspect='auto')
    axes[0, 0].set_title(f'{method1_name} RDM - Subject {subject_id}', fontsize=12, fontweight='bold')
    axes[0, 0].set_xlabel('Stimulus')
    axes[0, 0].set_ylabel('Stimulus')
    plt.colorbar(im1, ax=axes[0, 0])
    
    # Plot RDM 2
    im2 = axes[0, 1].imshow(rdm2_matrix, cmap='viridis', aspect='auto')
    axes[0, 1].set_title(f'{method2_name} RDM - Subject {subject_id}', fontsize=12, fontweight='bold')
    axes[0, 1].set_xlabel('Stimulus')
    axes[0, 1].set_ylabel('Stimulus')
    plt.colorbar(im2, ax=axes[0, 1])
    
    # Plot difference matrix
    # Normalize both to same scale for fair comparison
    rdm1_norm = safe_normalize(rdm1_matrix)
    rdm2_norm = safe_normalize(rdm2_matrix)
    diff = rdm1_norm - rdm2_norm
    
    im3 = axes[1, 0].imshow(diff, cmap='RdBu_r', aspect='auto', vmin=-1, vmax=1)
    axes[1, 0].set_title(f'Difference ({method1_name} - {method2_name})\nNormalized', 
                         fontsize=12, fontweight='bold')
    axes[1, 0].set_xlabel('Stimulus')
    axes[1, 0].set_ylabel('Stimulus')
    plt.colorbar(im3, ax=axes[1, 0])
    
    # Scatter plot of dissimilarities
    rdm1_lower = get_lower_triangle(rdm1_matrix)
    rdm2_lower = get_lower_triangle(rdm2_matrix)
    
    axes[1, 1].scatter(rdm1_lower, rdm2_lower, alpha=0.3, s=10)
    axes[1, 1].set_xlabel(f'{method1_name} Dissimilarity')
    axes[1, 1].set_ylabel(f'{method2_name} Dissimilarity')
    axes[1, 1].set_title(f'Dissimilarity Correspondence - Subject {subject_id}', 
                        fontsize=12, fontweight='bold')
    
    # Add correlation line (only if there is variation)
    if np.nanstd(rdm1_lower) > 0 and np.nanstd(rdm2_lower) > 0:
        z = np.polyfit(rdm1_lower, rdm2_lower, 1)
        p = np.poly1d(z)
        x_line = np.linspace(np.nanmin(rdm1_lower), np.nanmax(rdm1_lower), 100)
        axes[1, 1].plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=2, label='Linear fit')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig

def plot_normalized_scatter(rdm1_norm, rdm2_norm, subject_id, results, 
                           method1_name="Behavior", method2_name="Multi-arrangement"):
    """
    Create a scatter plot with normalized dissimilarities
    """
    fig, ax = plt.subplots(figsize=(8, 8))
    
    ax.scatter(rdm1_norm, rdm2_norm, alpha=0.4, s=20)
    ax.set_xlabel(f'{method1_name} Dissimilarity (normalized)', fontsize=12)
    ax.set_ylabel(f'{method2_name} Dissimilarity (normalized)', fontsize=12)
    ax.set_title(f'Normalized Dissimilarity Comparison - Subject {subject_id}\n' + 
                 f'Pearson r = {results["pearson_r"]:.3f}, Spearman ρ = {results["spearman_r"]:.3f}',
                 fontsize=13, fontweight='bold')
    
    # Add identity line
    ax.plot([0, 1], [0, 1], 'k--', alpha=0.5, linewidth=2, label='Identity line')
    
    # Add regression line (if data vary)
    if np.nanstd(rdm1_norm) > 0 and np.nanstd(rdm2_norm) > 0:
        z = np.polyfit(rdm1_norm, rdm2_norm, 1)
        p = np.poly1d(z)
        x_line = np.linspace(0, 1, 100)
        ax.plot(x_line, p(x_line), "r--", alpha=0.8, linewidth=2, label='Linear fit')
    
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1])
    
    plt.tight_layout()
    return fig

def format_ci(ci: Tuple[float, float]) -> str:
    return f"[{ci[0]:.4f}, {ci[1]:.4f}]"


def print_comparison_report(results, subject_id):
    """
    Print a formatted report of comparison metrics
    """
    print(f"\n{'='*70}")
    print(f"RDM COMPARISON REPORT - SUBJECT {subject_id}")
    print(f"{'='*70}")
    print(f"\nNumber of pairwise comparisons: {results['n_comparisons']}")
    print(f"\n--- Correlation Metrics ---")
    print(f"Pearson correlation:  r = {results['pearson_r']:.4f}, p = {results['pearson_p']:.4e}")
    print(f"Spearman correlation: ρ = {results['spearman_r']:.4f}, p = {results['spearman_p']:.4e}")
    print(f"\n--- Error Metrics (Raw Scale) ---")
    print(f"Root Mean Square Error (RMSE): {results['rmse']:.4f}")
    print(f"Mean Absolute Error (MAE):     {results['mae']:.4f}")
    print(f"\n--- Error Metrics (Normalized 0-1 Scale) ---")
    print(f"Root Mean Square Error (RMSE): {results['rmse_normalized']:.4f}")
    print(f"Mean Absolute Error (MAE):     {results['mae_normalized']:.4f}")

    print(f"\n--- Agreement Metrics ---")
    print(f"Concordance Correlation Coefficient: {results['ccc']:.4f}")
    if 'deming_slope' in results:
        slope_ci = format_ci(results.get('deming_slope_ci', (float('nan'), float('nan'))))
        intercept_ci = format_ci(results.get('deming_intercept_ci', (float('nan'), float('nan'))))
        print(f"Deming slope: {results['deming_slope']:.4f}")
        print(f"Deming intercept: {results['deming_intercept']:.4f}")
        print(f"Deming slope 95% CI: {slope_ci}")
        print(f"Deming intercept 95% CI: {intercept_ci}")
    mean_diff, loa = results['bland_altman_mean_diff'], results['bland_altman_loa']
    print(f"Bland–Altman mean diff: {mean_diff:.4f}")
    print(f"Bland–Altman LoA: [{loa[0]:.4f}, {loa[1]:.4f}]")
    print(f"\n{'='*70}\n")

def create_summary_comparison(results_sub1, results_sub2):
    """
    Create a summary comparison across both subjects
    """
    print(f"\n{'='*70}")
    print(f"SUMMARY COMPARISON ACROSS SUBJECTS")
    print(f"{'='*70}")
    
    # Create comparison table
    metrics = ['pearson_r', 'spearman_r', 'rmse_normalized', 'mae_normalized']
    metric_names = ['Pearson r', 'Spearman ρ', 'RMSE (norm)', 'MAE (norm)']
    
    print(f"\n{'Metric':<20} {'Subject 1':>15} {'Subject 2':>15} {'Mean':>15}")
    print(f"{'-'*70}")
    
    for metric, name in zip(metrics, metric_names):
        sub1_val = results_sub1[metric]
        sub2_val = results_sub2[metric]
        mean_val = (sub1_val + sub2_val) / 2
        print(f"{name:<20} {sub1_val:>15.4f} {sub2_val:>15.4f} {mean_val:>15.4f}")
    
    print(f"\n{'='*70}\n")
    
    # Create bar plot comparing subjects
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    subjects = ['Subject 1', 'Subject 2']
    
    # Pearson correlation
    pearson_vals = [results_sub1['pearson_r'], results_sub2['pearson_r']]
    axes[0, 0].bar(subjects, pearson_vals, color=['#1f77b4', '#ff7f0e'])
    axes[0, 0].set_ylabel('Correlation', fontsize=11)
    axes[0, 0].set_title('Pearson Correlation', fontsize=12, fontweight='bold')
    axes[0, 0].set_ylim([0, 1])
    axes[0, 0].grid(axis='y', alpha=0.3)
    
    # Spearman correlation
    spearman_vals = [results_sub1['spearman_r'], results_sub2['spearman_r']]
    axes[0, 1].bar(subjects, spearman_vals, color=['#1f77b4', '#ff7f0e'])
    axes[0, 1].set_ylabel('Correlation', fontsize=11)
    axes[0, 1].set_title('Spearman Correlation', fontsize=12, fontweight='bold')
    axes[0, 1].set_ylim([0, 1])
    axes[0, 1].grid(axis='y', alpha=0.3)
    
    # RMSE normalized
    rmse_vals = [results_sub1['rmse_normalized'], results_sub2['rmse_normalized']]
    axes[1, 0].bar(subjects, rmse_vals, color=['#1f77b4', '#ff7f0e'])
    axes[1, 0].set_ylabel('RMSE (normalized)', fontsize=11)
    axes[1, 0].set_title('Root Mean Square Error', fontsize=12, fontweight='bold')
    axes[1, 0].grid(axis='y', alpha=0.3)
    
    # MAE normalized
    mae_vals = [results_sub1['mae_normalized'], results_sub2['mae_normalized']]
    axes[1, 1].bar(subjects, mae_vals, color=['#1f77b4', '#ff7f0e'])
    axes[1, 1].set_ylabel('MAE (normalized)', fontsize=11)
    axes[1, 1].set_title('Mean Absolute Error', fontsize=12, fontweight='bold')
    axes[1, 1].grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    return fig


def _save_fig(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    try:
        rel = path.relative_to(Path.cwd())
    except ValueError:
        rel = path
    print(f"Saved: {rel}")


def _results_table(results_sub1: dict, results_sub2: dict) -> np.ndarray:
    subjects = ['Subject 1', 'Subject 2', 'Mean']
    pearson_r = np.array([
        results_sub1['pearson_r'],
        results_sub2['pearson_r'],
        (results_sub1['pearson_r'] + results_sub2['pearson_r']) / 2,
    ])
    pearson_p = np.array([
        results_sub1['pearson_p'],
        results_sub2['pearson_p'],
        np.nan,
    ])
    spearman_r = np.array([
        results_sub1['spearman_r'],
        results_sub2['spearman_r'],
        (results_sub1['spearman_r'] + results_sub2['spearman_r']) / 2,
    ])
    spearman_p = np.array([
        results_sub1['spearman_p'],
        results_sub2['spearman_p'],
        np.nan,
    ])
    rmse_norm = np.array([
        results_sub1['rmse_normalized'],
        results_sub2['rmse_normalized'],
        (results_sub1['rmse_normalized'] + results_sub2['rmse_normalized']) / 2,
    ])
    mae_norm = np.array([
        results_sub1['mae_normalized'],
        results_sub2['mae_normalized'],
        (results_sub1['mae_normalized'] + results_sub2['mae_normalized']) / 2,
    ])

    table = np.column_stack([
        subjects,
        pearson_r,
        pearson_p,
        spearman_r,
        spearman_p,
        rmse_norm,
        mae_norm,
    ])
    return table


def _print_results_table(table: np.ndarray) -> None:
    print(f"\n{'Subject':<15} {'Pearson r':>12} {'Pearson p':>12} {'Spearman ρ':>12} {'Spearman p':>12} {'RMSE(norm)':>12} {'MAE(norm)':>12}")
    print("-" * 100)
    for row in table:
        subject = row[0]
        pearson_r, pearson_p, spearman_r, spearman_p, rmse_norm, mae_norm = row[1:]
        p_str = f"{float(pearson_p):.2e}" if not np.isnan(float(pearson_p)) else "   --    "
        s_str = f"{float(spearman_p):.2e}" if not np.isnan(float(spearman_p)) else "   --    "
        print(
            f"{subject:<15} {float(pearson_r):>12.4f} {p_str:>12} {float(spearman_r):>12.4f} {s_str:>12} {float(rmse_norm):>12.4f} {float(mae_norm):>12.4f}"
        )
    print("")


def _write_results_csv(table: np.ndarray, output_path: Path) -> None:
    header = "Subject,Pearson_r,Pearson_p,Spearman_rho,Spearman_p,RMSE_normalized,MAE_normalized\n"
    with output_path.open('w', encoding='utf-8') as f:
        f.write(header)
        for row in table:
            f.write(
                f"{row[0]},{float(row[1])},{row[2]},{float(row[3])},{row[4]},{float(row[5])},{float(row[6])}\n"
            )
    try:
        rel = output_path.relative_to(Path.cwd())
    except ValueError:
        rel = output_path
    print(f"Saved: {rel}")


def run_analysis(
    *,
    output_dir: Optional[Path] = None,
    seed: int = DEFAULT_SEED,
    bootstrap_samples: int = BOOTSTRAP_SAMPLES,
    alpha: float = 0.05,
    verbose: bool = True,
):
    """Execute the full RDM comparison analysis pipeline."""

    set_global_seeds(seed)
    rng_master = np.random.default_rng(seed)

    base_dir = Path(__file__).resolve().parent
    data_paths = {
        'behavior_sub1': base_dir / 'BehaviorSub1_rdm_normalized.csv',
        'behavior_sub2': base_dir / 'BehaviorSub2_rdm_normalized.csv',
        'ma_sub1': base_dir / 'rdm_sub1_ma_normalized.csv',
        'ma_sub2': base_dir / 'rdm_sub2_ma_normalized.csv',
    }

    for path in data_paths.values():
        if not path.exists():
            raise FileNotFoundError(f"Required data file not found: {path}")

    if output_dir is None:
        output_dir = base_dir
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("\n" + "=" * 70)
        print("RDM COMPARISON ANALYSIS: Behavior vs Multi-arrangement Methods")
        print("=" * 70)
        print("\nLoading data files...")

    behavior_sub1, _ = load_rdm(data_paths['behavior_sub1'])
    ma_sub1, _ = load_rdm(data_paths['ma_sub1'])
    behavior_sub2, _ = load_rdm(data_paths['behavior_sub2'])
    ma_sub2, _ = load_rdm(data_paths['ma_sub2'])

    if verbose:
        print("Data loaded successfully!")

    rng_sub1 = np.random.default_rng(rng_master.integers(0, 2**32 - 1))
    rng_sub2 = np.random.default_rng(rng_master.integers(0, 2**32 - 1))

    if verbose:
        print("\n" + "=" * 70)
        print("ANALYZING SUBJECT 1")
        print("=" * 70)

    results_sub1, rdm1_lower, rdm2_lower, rdm1_norm, rdm2_norm = compare_rdms(
        behavior_sub1,
        ma_sub1,
        "Behavior",
        "Multi-arrangement",
        bootstrap_samples=bootstrap_samples,
        rng=rng_sub1,
    )
    if verbose:
        print_comparison_report(results_sub1, 1)

    fig1 = plot_rdm_comparison(behavior_sub1, ma_sub1, 1)
    _save_fig(fig1, output_dir / 'subject1_rdm_comparison.png')

    fig1_scatter = plot_normalized_scatter(rdm1_norm, rdm2_norm, 1, results_sub1)
    _save_fig(fig1_scatter, output_dir / 'subject1_normalized_scatter.png')

    if verbose:
        print("\n" + "=" * 70)
        print("ANALYZING SUBJECT 2")
        print("=" * 70)

    results_sub2, rdm1_lower_s2, rdm2_lower_s2, rdm1_norm_s2, rdm2_norm_s2 = compare_rdms(
        behavior_sub2,
        ma_sub2,
        "Behavior",
        "Multi-arrangement",
        bootstrap_samples=bootstrap_samples,
        rng=rng_sub2,
    )
    if verbose:
        print_comparison_report(results_sub2, 2)

    fig2 = plot_rdm_comparison(behavior_sub2, ma_sub2, 2)
    _save_fig(fig2, output_dir / 'subject2_rdm_comparison.png')

    fig2_scatter = plot_normalized_scatter(rdm1_norm_s2, rdm2_norm_s2, 2, results_sub2)
    _save_fig(fig2_scatter, output_dir / 'subject2_normalized_scatter.png')

    fig_summary = create_summary_comparison(results_sub1, results_sub2)
    _save_fig(fig_summary, output_dir / 'summary_comparison.png')

    if verbose:
        print("\n" + "=" * 70)
        print("RESULTS TABLE FOR MANUSCRIPT")
        print("=" * 70)

    table = _results_table(results_sub1, results_sub2)
    if verbose:
        _print_results_table(table)

    _write_results_csv(table, output_dir / 'comparison_results_table.csv')

    if verbose:
        print("\n" + "=" * 70)
        print("ANALYSIS COMPLETE!")
        print("=" * 70)
        print("\nGenerated files:")
        for name in [
            'subject1_rdm_comparison.png',
            'subject1_normalized_scatter.png',
            'subject2_rdm_comparison.png',
            'subject2_normalized_scatter.png',
            'summary_comparison.png',
            'comparison_results_table.csv',
        ]:
            print(f"  - {name}")
        print("\n" + "=" * 70 + "\n")

    summary_metrics = {
        'pearson_mean': (results_sub1['pearson_r'] + results_sub2['pearson_r']) / 2,
        'spearman_mean': (results_sub1['spearman_r'] + results_sub2['spearman_r']) / 2,
        'rmse_norm_mean': (results_sub1['rmse_normalized'] + results_sub2['rmse_normalized']) / 2,
        'mae_norm_mean': (results_sub1['mae_normalized'] + results_sub2['mae_normalized']) / 2,
    }

    return {
        'subject_1': results_sub1,
        'subject_2': results_sub2,
        'summary': summary_metrics,
        'output_dir': output_dir,
    }


def main():
    run_analysis()

if __name__ == "__main__":
    main()

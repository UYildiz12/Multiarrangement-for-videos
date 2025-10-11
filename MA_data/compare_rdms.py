"""
RDM Comparison Script for Research Methods Paper
Compares two different data collection methods for measuring representational dissimilarity
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, pearsonr
from scipy.spatial.distance import squareform
from sklearn.metrics import mean_squared_error, mean_absolute_error
import os

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

def compare_rdms(rdm1_matrix, rdm2_matrix, method1_name="Method 1", method2_name="Method 2"):
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

def main():
    """
    Main function to run the RDM comparison analysis
    """
    print("\n" + "="*70)
    print("RDM COMPARISON ANALYSIS: Behavior vs Multi-arrangement Methods")
    print("="*70)
    
    # Load data
    print("\nLoading data files...")
    base_dir = os.path.dirname(__file__)
    behavior_sub1_fp = os.path.join(base_dir, 'BehaviorSub1_rdm_normalized.csv')
    behavior_sub2_fp = os.path.join(base_dir, 'BehaviorSub2_rdm_normalized.csv')
    ma_sub1_fp = os.path.join(base_dir, 'rdm_sub1_ma_normalized.csv')
    ma_sub2_fp = os.path.join(base_dir, 'rdm_sub2_ma_normalized.csv')

    # Check files exist
    for p in [behavior_sub1_fp, behavior_sub2_fp, ma_sub1_fp, ma_sub2_fp]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Required data file not found: {p}")

    behavior_sub1, labels1 = load_rdm(behavior_sub1_fp)
    ma_sub1, _ = load_rdm(ma_sub1_fp)
    behavior_sub2, labels2 = load_rdm(behavior_sub2_fp)
    ma_sub2, _ = load_rdm(ma_sub2_fp)
    print("Data loaded successfully!")
    
    # Subject 1 analysis
    print("\n" + "="*70)
    print("ANALYZING SUBJECT 1")
    print("="*70)
    results_sub1, rdm1_lower, rdm2_lower, rdm1_norm, rdm2_norm = compare_rdms(
        behavior_sub1, ma_sub1, "Behavior", "Multi-arrangement"
    )
    print_comparison_report(results_sub1, 1)
    
    # Create visualizations for Subject 1
    fig1 = plot_rdm_comparison(behavior_sub1, ma_sub1, 1)
    fig1.savefig('subject1_rdm_comparison.png', dpi=300, bbox_inches='tight')
    print("Saved: subject1_rdm_comparison.png")
    
    fig1_scatter = plot_normalized_scatter(rdm1_norm, rdm2_norm, 1, results_sub1)
    fig1_scatter.savefig('subject1_normalized_scatter.png', dpi=300, bbox_inches='tight')
    print("Saved: subject1_normalized_scatter.png")
    
    # Subject 2 analysis
    print("\n" + "="*70)
    print("ANALYZING SUBJECT 2")
    print("="*70)
    results_sub2, rdm1_lower_s2, rdm2_lower_s2, rdm1_norm_s2, rdm2_norm_s2 = compare_rdms(
        behavior_sub2, ma_sub2, "Behavior", "Multi-arrangement"
    )
    print_comparison_report(results_sub2, 2)
    
    # Create visualizations for Subject 2
    fig2 = plot_rdm_comparison(behavior_sub2, ma_sub2, 2)
    fig2.savefig('subject2_rdm_comparison.png', dpi=300, bbox_inches='tight')
    print("Saved: subject2_rdm_comparison.png")
    
    fig2_scatter = plot_normalized_scatter(rdm1_norm_s2, rdm2_norm_s2, 2, results_sub2)
    fig2_scatter.savefig('subject2_normalized_scatter.png', dpi=300, bbox_inches='tight')
    print("Saved: subject2_normalized_scatter.png")
    
    # Summary comparison
    fig_summary = create_summary_comparison(results_sub1, results_sub2)
    fig_summary.savefig('summary_comparison.png', dpi=300, bbox_inches='tight')
    print("Saved: summary_comparison.png")
    
    # Create a combined results table for easy reporting
    print("\n" + "="*70)
    print("RESULTS TABLE FOR MANUSCRIPT")
    print("="*70)
    
    # Create data manually as lists
    subjects = ['Subject 1', 'Subject 2', 'Mean']
    pearson_r = [
        results_sub1['pearson_r'], 
        results_sub2['pearson_r'],
        (results_sub1['pearson_r'] + results_sub2['pearson_r']) / 2
    ]
    pearson_p = [
        results_sub1['pearson_p'], 
        results_sub2['pearson_p'],
        np.nan
    ]
    spearman_r = [
        results_sub1['spearman_r'], 
        results_sub2['spearman_r'],
        (results_sub1['spearman_r'] + results_sub2['spearman_r']) / 2
    ]
    spearman_p = [
        results_sub1['spearman_p'], 
        results_sub2['spearman_p'],
        np.nan
    ]
    rmse_norm = [
        results_sub1['rmse_normalized'], 
        results_sub2['rmse_normalized'],
        (results_sub1['rmse_normalized'] + results_sub2['rmse_normalized']) / 2
    ]
    mae_norm = [
        results_sub1['mae_normalized'], 
        results_sub2['mae_normalized'],
        (results_sub1['mae_normalized'] + results_sub2['mae_normalized']) / 2
    ]
    
    # Print table without pandas
    print(f"\n{'Subject':<15} {'Pearson r':>12} {'Pearson p':>12} {'Spearman ρ':>12} {'Spearman p':>12} {'RMSE(norm)':>12} {'MAE(norm)':>12}")
    print("-" * 100)
    for i in range(3):
        p_str = f"{pearson_p[i]:.2e}" if not np.isnan(pearson_p[i]) else "   --    "
        s_str = f"{spearman_p[i]:.2e}" if not np.isnan(spearman_p[i]) else "   --    "
        print(f"{subjects[i]:<15} {pearson_r[i]:>12.4f} {p_str:>12} {spearman_r[i]:>12.4f} {s_str:>12} {rmse_norm[i]:>12.4f} {mae_norm[i]:>12.4f}")
    print("")
    
    # Save to CSV manually
    with open('comparison_results_table.csv', 'w') as f:
        f.write("Subject,Pearson_r,Pearson_p,Spearman_rho,Spearman_p,RMSE_normalized,MAE_normalized\n")
        for i in range(3):
            f.write(f"{subjects[i]},{pearson_r[i]},{pearson_p[i]},{spearman_r[i]},{spearman_p[i]},{rmse_norm[i]},{mae_norm[i]}\n")
    print("Saved: comparison_results_table.csv")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE!")
    print("="*70)
    print("\nGenerated files:")
    print("  - subject1_rdm_comparison.png")
    print("  - subject1_normalized_scatter.png")
    print("  - subject2_rdm_comparison.png")
    print("  - subject2_normalized_scatter.png")
    print("  - summary_comparison.png")
    print("  - comparison_results_table.csv")
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    main()

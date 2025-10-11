"""Command-line helper to reproduce the MA_data analysis outputs."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Tuple

from MA_data import compare_rdms

DEFAULT_SEED = compare_rdms.DEFAULT_SEED
DEFAULT_BOOTSTRAP = compare_rdms.BOOTSTRAP_SAMPLES
_ANALYSIS_FILE = Path('MA_data') / 'analysis_results.txt'


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce the MA_data figures, tables, and summary statistics.",
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Directory for the generated figures and CSV (defaults to MA_data).',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=DEFAULT_SEED,
        help=f'Random seed used for the bootstrap (default: {DEFAULT_SEED}).',
    )
    parser.add_argument(
        '--bootstrap-samples',
        type=int,
        default=DEFAULT_BOOTSTRAP,
        help=f'Number of bootstrap samples for the Deming CI (default: {DEFAULT_BOOTSTRAP}).',
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress the verbose narrative log and only print the summary table.',
    )
    return parser.parse_args()


def _load_expected_metrics(path: Path) -> Dict[str, Dict[str, Tuple[float, ...]]]:
    """Parse key numbers from analysis_results.txt for comparison."""

    if not path.exists():
        return {}

    section = None
    metrics: Dict[str, Dict[str, Tuple[float, ...]]] = {}
    float_pattern = re.compile(r'-?\d+\.\d+(?:e[+-]?\d+)?', re.IGNORECASE)

    with path.open('r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('SUBJECT 1'):
                section = 'subject_1'
                metrics[section] = {}
                continue
            if line.startswith('SUBJECT 2'):
                section = 'subject_2'
                metrics[section] = {}
                continue
            if line.startswith('SUMMARY'):
                section = 'summary'
                metrics[section] = {}
                continue
            if section is None:
                continue

            if ':' not in line:
                continue
            key, rest = line.split(':', 1)
            values = tuple(float(x) for x in float_pattern.findall(rest))
            metrics.setdefault(section, {})[key.strip()] = values

    return metrics


def _format_subject_report(name: str, stats: Dict[str, float]) -> str:
    return (
        f"{name}: "
        f"Pearson r={stats['pearson_r']:.4f}, Spearman ρ={stats['spearman_r']:.4f}, "
        f"RMSE(raw)={stats['rmse']:.4f}, MAE(raw)={stats['mae']:.4f}, "
        f"RMSE(norm)={stats['rmse_normalized']:.4f}, MAE(norm)={stats['mae_normalized']:.4f}, "
        f"CCC={stats['ccc']:.4f}, Deming slope={stats['deming_slope']:.4f}, "
        f"Deming intercept={stats['deming_intercept']:.4f}, "
        f"Bland–Altman mean diff={stats['bland_altman_mean_diff']:.4f}"
    )


def _compare_to_expected(
    computed: Dict[str, Dict[str, float]],
    expected: Dict[str, Dict[str, Tuple[float, ...]]],
    *,
    tolerance: float = 5e-3,
) -> None:
    if not expected:
        print("Expected metrics file not found; skipping comparison.")
        return

    print("\nChecking against analysis_results.txt…")
    for section_name, stats in computed.items():
        target = expected.get(section_name, {})
        for label, value in stats.items():
            if isinstance(value, tuple):
                # Compare tuple metrics (CIs, LoA)
                expected_vals = target.get(label, ())
                if len(expected_vals) == len(value):
                    diffs = [abs(a - b) for a, b in zip(value, expected_vals)]
                    status = all(d <= tolerance for d in diffs)
                    diff_str = ', '.join(f"Δ={d:.4f}" for d in diffs)
                    print(f"  [{section_name}] {label}: computed {value} vs expected {expected_vals} ({diff_str}) {'✔' if status else '⚠'}")
                continue
            expected_vals = target.get(label)
            if not expected_vals:
                continue
            diff = abs(value - expected_vals[0])
            status = diff <= tolerance
            print(
                f"  [{section_name}] {label}: computed {value:.4f} vs expected {expected_vals[0]:.4f} Δ={diff:.4f} {'✔' if status else '⚠'}"
            )


def main() -> None:
    args = _parse_args()

    results = compare_rdms.run_analysis(
        output_dir=args.output_dir,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
        verbose=not args.quiet,
    )

    subject1 = results['subject_1']
    subject2 = results['subject_2']
    summary = results['summary']

    print("\nKey statistics matching analysis_results.txt:")
    print("  " + _format_subject_report('Subject 1', subject1))
    print("  " + _format_subject_report('Subject 2', subject2))
    print(
        "  Summary: "
        f"mean Pearson={summary['pearson_mean']:.4f}, mean Spearman={summary['spearman_mean']:.4f}, "
        f"mean RMSE(norm)={summary['rmse_norm_mean']:.4f}, mean MAE(norm)={summary['mae_norm_mean']:.4f}"
    )

    computed = {
        'subject_1': {
            'Pearson r': subject1['pearson_r'],
            'Spearman rho': subject1['spearman_r'],
            'RMSE (raw)': subject1['rmse'],
            'MAE  (raw)': subject1['mae'],
            'RMSE (norm)': subject1['rmse_normalized'],
            'MAE  (norm)': subject1['mae_normalized'],
            'CCC': subject1['ccc'],
            'Deming slope': subject1['deming_slope'],
            'Deming intcpt': subject1['deming_intercept'],
            'Deming slope 95% CI': subject1.get('deming_slope_ci', tuple()),
            'Deming intcpt 95% CI': subject1.get('deming_intercept_ci', tuple()),
            'Bland–Altman mean diff': subject1['bland_altman_mean_diff'],
            'Bland–Altman LoA': subject1['bland_altman_loa'],
        },
        'subject_2': {
            'Pearson r': subject2['pearson_r'],
            'Spearman rho': subject2['spearman_r'],
            'RMSE (raw)': subject2['rmse'],
            'MAE  (raw)': subject2['mae'],
            'RMSE (norm)': subject2['rmse_normalized'],
            'MAE  (norm)': subject2['mae_normalized'],
            'CCC': subject2['ccc'],
            'Deming slope': subject2['deming_slope'],
            'Deming intcpt': subject2['deming_intercept'],
            'Deming slope 95% CI': subject2.get('deming_slope_ci', tuple()),
            'Deming intcpt 95% CI': subject2.get('deming_intercept_ci', tuple()),
            'Bland–Altman mean diff': subject2['bland_altman_mean_diff'],
            'Bland–Altman LoA': subject2['bland_altman_loa'],
        },
        'summary': {
            'Pearson r mean': summary['pearson_mean'],
            'Spearman rho mean': summary['spearman_mean'],
            'RMSE (norm) mean': summary['rmse_norm_mean'],
            'MAE  (norm) mean': summary['mae_norm_mean'],
        },
    }

    expected = _load_expected_metrics(_ANALYSIS_FILE)
    _compare_to_expected(computed, expected)


if __name__ == '__main__':  # pragma: no cover
    main()

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from multiarrangement.results import Results


matplotlib.use("Agg")


def _sample_matrix() -> np.ndarray:
    return np.array(
        [
            [0.0, 1.5, 2.0],
            [1.5, 0.0, 0.8],
            [2.0, 0.8, 0.0],
        ],
        dtype=float,
    )


def test_results_loaders_round_trip(tmp_path: Path):
    matrix = _sample_matrix()
    labels = ["clip_a", "clip_b", "clip_c"]
    df = pd.DataFrame(matrix, index=labels, columns=labels)

    csv_path = tmp_path / "rdm.csv"
    excel_path = tmp_path / "rdm.xlsx"
    npy_path = tmp_path / "rdm.npy"

    df.to_csv(csv_path)
    df.to_excel(excel_path)
    np.save(npy_path, matrix)

    csv_results = Results.from_csv(csv_path)
    excel_results = Results.from_excel(excel_path)
    npy_results = Results.from_npy(npy_path, labels=labels)

    assert csv_results.labels == labels
    assert excel_results.labels == labels
    assert npy_results.labels == labels
    assert np.allclose(csv_results.matrix, matrix)
    assert np.allclose(excel_results.matrix, matrix)
    assert np.allclose(npy_results.matrix, matrix)


def test_results_savefig_and_vis_write_output(tmp_path: Path):
    results = Results(matrix=_sample_matrix(), labels=["a", "b", "c"])
    png_path = tmp_path / "rdm.png"
    pdf_path = tmp_path / "rdm.pdf"

    results.savefig(png_path, title="Set-cover RDM")
    results.vis(title="Adaptive LTW RDM", save=pdf_path, show=False, annotate=True)

    assert png_path.exists()
    assert pdf_path.exists()
    assert png_path.stat().st_size > 0
    assert pdf_path.stat().st_size > 0

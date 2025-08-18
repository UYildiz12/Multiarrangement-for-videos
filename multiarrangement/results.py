from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd


@dataclass
class Results:
    """Container for multiarrangement results with convenient visualization.

    Attributes:
        matrix: Square dissimilarity matrix (n x n)
        labels: Optional list of item labels (length n)
        meta: Optional dictionary for extra info (file paths, config, etc.)
    """

    matrix: np.ndarray
    labels: Optional[List[str]] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_csv(cls, path: str | Path) -> "Results":
        df = pd.read_csv(path, index_col=0)
        mat = df.to_numpy(dtype=float)
        labels = list(df.index.astype(str))
        return cls(matrix=mat, labels=labels, meta={"csv_path": str(path)})

    @classmethod
    def from_excel(cls, path: str | Path) -> "Results":
        df = pd.read_excel(path, index_col=0)
        mat = df.to_numpy(dtype=float)
        labels = list(df.index.astype(str))
        return cls(matrix=mat, labels=labels, meta={"excel_path": str(path)})

    @classmethod
    def from_npy(cls, path: str | Path, labels: Optional[List[str]] = None) -> "Results":
        mat = np.load(path).astype(float)
        return cls(matrix=mat, labels=labels, meta={"npy_path": str(path)})

    def vis(
        self,
        *,
        title: Optional[str] = None,
        cmap: str = "viridis",
        figsize: tuple[int, int] = (8, 6),
        show: bool = True,
        save: Optional[str | Path] = None,
        colorbar: bool = True,
        annotate: bool = False,
    ) -> None:
        """Display a heatmap of the dissimilarity matrix using matplotlib.

        Args:
            title: Optional title for the plot
            cmap: Matplotlib colormap
            figsize: Figure size
            show: Whether to call plt.show()
            save: Optional path to save the figure
            colorbar: Whether to draw a colorbar
            annotate: If True, draw numeric values for small matrices (n<=20 recommended)
        """
        import matplotlib.pyplot as plt

        M = np.array(self.matrix, dtype=float)
        n = M.shape[0]
        fig, ax = plt.subplots(figsize=figsize)
        im = ax.imshow(M, cmap=cmap, interpolation="nearest", aspect="equal")

        # Ticks and labels: always show all item names
        if self.labels is not None and len(self.labels) == n:
            xlabels = list(self.labels)
            ylabels = list(self.labels)
        else:
            xlabels = [str(i) for i in range(n)]
            ylabels = [str(i) for i in range(n)]
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(xlabels, rotation=90)
        ax.set_yticklabels(ylabels)
        ax.tick_params(axis='both', which='both', labelsize=8)

        if colorbar:
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        if title:
            ax.set_title(title)

        if annotate and n <= 20:
            for i in range(n):
                for j in range(n):
                    ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", color="w", fontsize=8)

        fig.tight_layout()
        if save:
            plt.savefig(save, dpi=150, bbox_inches="tight")
        if show:
            plt.show()

    def savefig(self, path: str | Path, **kwargs) -> None:
        """Save a heatmap of the dissimilarity matrix to an image file.

        Args:
            path: Output file path (e.g., 'rdm.png' or 'rdm.pdf')
            **kwargs: Extra keyword args forwarded to vis (e.g., title, cmap)
        """
        # Force non-interactive save
        kwargs = dict(kwargs)
        kwargs.setdefault("show", False)
        kwargs["save"] = path
        self.vis(**kwargs)

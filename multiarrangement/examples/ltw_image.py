from pathlib import Path
import multiarrangement as ma
from multiarrangement.utils.file_utils import resolve_packaged_dir


def main() -> None:
    input_dir = str(resolve_packaged_dir("15images"))
    Path("results").mkdir(exist_ok=True)
    res = ma.multiarrangement_adaptive(
        input_dir,
        output_dir="results",
        fullscreen=True,
        evidence_threshold=0.35,
        min_subset_size=4,
        max_subset_size=6,
        use_inverse_mds=True,
    )
    if res is not None:
        res.vis(title="Adaptive LTW RDM (image)")
        res.savefig("results/rdm_adaptive_image.png", title="Adaptive LTW RDM (image)")


if __name__ == "__main__":
    main()


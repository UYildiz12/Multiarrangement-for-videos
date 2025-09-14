from pathlib import Path
import multiarrangement as ma
from multiarrangement.utils.file_utils import resolve_packaged_dir


def main() -> None:
    try:
        input_dir = str(resolve_packaged_dir("15audios"))
    except FileNotFoundError:
        input_dir = str(resolve_packaged_dir("sample_audio"))

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
    res.vis(title="Adaptive LTW RDM (audio)")
    res.savefig("results/rdm_adaptive_audio.png", title="Adaptive LTW RDM (audio)")


if __name__ == "__main__":
    main()

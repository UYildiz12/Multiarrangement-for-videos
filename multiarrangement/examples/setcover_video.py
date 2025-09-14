from pathlib import Path
import multiarrangement as ma
from multiarrangement.utils.file_utils import resolve_packaged_dir


def main() -> None:
    input_dir = str(resolve_packaged_dir("15videos"))
    n = ma.auto_detect_stimuli(input_dir)
    batches = ma.create_batches(n, 8, algorithm="python")

    Path("results").mkdir(exist_ok=True)
    res = ma.multiarrangement(input_dir, batches, output_dir="results", fullscreen=False)
    res.vis(title="Set‑Cover RDM (video)")
    res.savefig("results/rdm_setcover_video.png", title="Set‑Cover RDM (video)")


if __name__ == "__main__":
    main()

from pathlib import Path
import multiarrangement as ma
from multiarrangement.utils.file_utils import resolve_packaged_dir


def main() -> None:
    # Prefer packaged 15images
    input_dir = str(resolve_packaged_dir("15images"))

    n = ma.auto_detect_stimuli(input_dir)
    # Choose a reasonable batch size for small n
    k = 6 if n >= 6 else max(3, n)
    batches = ma.create_batches(n, k, algorithm="python")

    Path("results").mkdir(exist_ok=True)
    res = ma.multiarrangement(input_dir, batches, output_dir="results", fullscreen=False)
    res.vis(title="Set‑Cover RDM (image)")
    res.savefig("results/rdm_setcover_image.png", title="Set‑Cover RDM (image)")


if __name__ == "__main__":
    main()


from pathlib import Path
import multiarrangement as ma
from multiarrangement.utils.file_utils import resolve_packaged_dir


def main() -> None:
    # Prefer packaged 15audios; fallback to sample_audio
    try:
        input_dir = str(resolve_packaged_dir("15audios"))
    except FileNotFoundError:
        input_dir = str(resolve_packaged_dir("sample_audio"))

    n = ma.auto_detect_stimuli(input_dir)
    k = 6 if n >= 6 else max(3, n)
    batches = ma.create_batches(n, k, algorithm="python")

    Path("results").mkdir(exist_ok=True)
    res = ma.multiarrangement(input_dir, batches, output_dir="results", fullscreen=False)
    res.vis(title="Set‑Cover RDM (audio)")
    res.savefig("results/rdm_setcover_audio.png", title="Set‑Cover RDM (audio)")


if __name__ == "__main__":
    main()

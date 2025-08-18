from pathlib import Path
import multiarrangement as ma


def _resolve_media_dir(name: str) -> str:
    base = Path(ma.__file__).parent
    p = base / name
    if p.exists():
        return str(p)
    for root in (base.parent, Path.cwd()):
        q = root / name
        if q.exists():
            return str(q)
    raise FileNotFoundError(f"Media '{name}' not found under {base}, {base.parent}, or {Path.cwd()}")


def main() -> None:
    # Prefer packaged 15audios; fallback to sample_audio
    try:
        input_dir = _resolve_media_dir("15audios")
    except FileNotFoundError:
        input_dir = _resolve_media_dir("sample_audio")

    n = ma.auto_detect_stimuli(input_dir)
    k = 6 if n >= 6 else max(3, n)
    batches = ma.create_batches(n, k, algorithm="python")

    Path("results").mkdir(exist_ok=True)
    res = ma.multiarrangement(input_dir, batches, output_dir="results", fullscreen=False)
    res.vis(title="Set‑Cover RDM (audio)")
    res.savefig("results/rdm_setcover_audio.png", title="Set‑Cover RDM (audio)")


if __name__ == "__main__":
    main()

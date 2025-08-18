from pathlib import Path
import multiarrangement as ma


def _resolve_media_dir(name: str) -> str:
    base = Path(ma.__file__).parent
    # Prefer packaged path
    p = base / name
    if p.exists():
        return str(p)
    # Fallbacks: repo root or current working directory
    for root in (base.parent, Path.cwd()):
        q = root / name
        if q.exists():
            return str(q)
    raise FileNotFoundError(f"Media '{name}' not found under {base}, {base.parent}, or {Path.cwd()}")


def main() -> None:
    input_dir = _resolve_media_dir("15videos")
    n = ma.auto_detect_stimuli(input_dir)
    batches = ma.create_batches(n, 8, algorithm="python")

    Path("results").mkdir(exist_ok=True)
    res = ma.multiarrangement(input_dir, batches, output_dir="results", fullscreen=False)
    res.vis(title="Set‑Cover RDM (video)")
    res.savefig("results/rdm_setcover_video.png", title="Set‑Cover RDM (video)")


if __name__ == "__main__":
    main()

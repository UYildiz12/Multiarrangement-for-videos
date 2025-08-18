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
    input_dir = _resolve_media_dir("15videos")
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
    res.vis(title="Adaptive LTW RDM (video)")
    res.savefig("results/rdm_adaptive_video.png", title="Adaptive LTW RDM (video)")


if __name__ == "__main__":
    main()

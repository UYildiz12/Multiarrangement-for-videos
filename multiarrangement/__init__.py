"""
Multiarrangement — Video & Audio Similarity Arrangement Toolkit.

This package provides tools for collecting human similarity judgements by
arranging stimuli (videos or audio) in a circular arena and converting the
placements into a full Representational Dissimilarity Matrix (RDM).

Demo Videos Source:
The demo videos included in this package are derived from:
Urgen, B. A., Nizamoğlu, H., Eroğlu, A., & Orban, G. A. (2023). A Large Video Set of Natural Human Actions 
for Visual and Cognitive Neuroscience Studies and Its Validation with fMRI. Brain Sciences, 
13(1), 61. https://doi.org/10.3390/brainsci13010061
"""

__version__ = "0.1.10.2"
__author__ = "Multiarrangement Team"

from .core.experiment import MultiarrangementExperiment
from .ui.interface import MultiarrangementInterface
from .utils.video_processing import VideoProcessor
from .utils.data_processing import DataProcessor
from .core.batch_generator import BatchGenerator
from typing import List, Optional
from .adaptive.adaptive_experiment import AdaptiveMultiarrangementExperiment, AdaptiveConfig
from .results import Results

# Main library functions
def create_batches(n_videos_or_file, batch_size: int = None, seed: int = 42, algorithm: str = 'hybrid', 
                   flex: bool = False):
    """
    Create or load batches for multiarrangement experiments.
    
    Args:
        n_videos_or_file: Either:
            - int: Total number of videos (creates new batches)
            - str/Path: Path to existing batch file (loads from file)
        batch_size: Number of items per batch (only used when creating new batches)
        seed: Random seed for reproducibility (only used when creating new batches)
        algorithm: Algorithm to use ('hybrid', 'optimal', 'greedy') (only used when creating new batches)
        flex: If True, use optimize_cover_flex.py for variable-size batch optimization
    
    Returns:
        List of batches, where each batch is a list of video indices
    
         Examples:
         # Create new batches
         >>> import multiarrangement as ma
         >>> batches = ma.create_batches(24, 8)
         >>> print(f"Created {len(batches)} batches")
         
         # Load existing batch file
         >>> batches = ma.create_batches("batches_24videos_batchsize8.txt")
         >>> print(f"Loaded {len(batches)} batches")
         
         # Use flexible batch sizes with optimize_cover_flex.py
         >>> batches = ma.create_batches(36, 8, flex=True)
         >>> print(f"Created {len(batches)} flexible batches")
    """
    from pathlib import Path
    from .utils.file_utils import load_batches
    
    # Check if input is a file path (string or Path object)
    if isinstance(n_videos_or_file, (str, Path)):
        batch_file = Path(n_videos_or_file)
        if batch_file.exists():
            print(f"📁 Loading batches from: {batch_file}")
            batches = load_batches(batch_file)
            print(f"✅ Loaded {len(batches)} batches from file")
            return batches
        else:
            raise FileNotFoundError(f"Batch file not found: {batch_file}")
    
    # Otherwise, treat as number of videos and create new batches
    n_videos = int(n_videos_or_file)
    if batch_size is None:
        raise ValueError("batch_size is required when creating new batches")
    
    # Handle flex mode with optimize_cover_flex.py
    if flex:
        print(f"🔧 Creating flexible batches for {n_videos} videos, initial batch size {batch_size}")
        mink = 2  # Hardcoded for maximum flexibility and performance
        batches = _create_flexible_batches(n_videos, batch_size, mink, seed, algorithm)
    else:
        print(f"🔧 Creating batches for {n_videos} videos, batch size {batch_size}")
        generator = BatchGenerator(n_videos=n_videos, batch_size=batch_size, seed=seed)
        batches = generator.optimize_batches(algorithm=algorithm)
    
    # Automatic validation
    validate_batches(batches, n_videos)
    
    return batches

def _create_flexible_batches(n_videos: int, batch_size: int, mink: int, seed: int, algorithm: str) -> List[List[int]]:
    """
    Create flexible batches using optimize_cover_flex.py.
    
    Args:
        n_videos: Total number of videos
        batch_size: Initial batch size (k parameter for LJCR)
        mink: Minimum batch size after optimization (hardcoded to 2)
        seed: Random seed for reproducibility
        algorithm: Algorithm preference (not used in flex mode)
        
    Returns:
        List of batches with variable sizes (each batch is a list of video indices)
    """
    import subprocess
    import tempfile
    import os
    from .utils.file_utils import resolve_packaged_dir
    from pathlib import Path
    
    # Try to find optimize_cover_flex.py in multiple locations
    flex_script = None
    
    # 1. Try current working directory (for development)
    cwd_script = Path.cwd() / "multiarrangement/optimize_cover_flex.py"
    if cwd_script.exists():
        flex_script = cwd_script
    
    # 2. Try package directory
    if flex_script is None:
        try:
            import multiarrangement
            package_dir = Path(multiarrangement.__file__).parent
            package_script = package_dir / "optimize_cover_flex.py"
            if package_script.exists():
                flex_script = package_script
        except ImportError:
            pass
    
    # 3. Try project root
    if flex_script is None:
        project_root = Path(__file__).parent.parent
        project_script = project_root / "multiarrangement/optimize_cover_flex.py"
        if project_script.exists():
            flex_script = project_script
    
    if flex_script is None:
        raise FileNotFoundError("optimize_cover_flex.py not found. Please ensure it's available in the multiarrangement package.")
    
    # Create temporary output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        output_file = f.name
    
    try:
        # Run optimize_cover_flex.py with correct arguments
        cmd = [
            "python", str(flex_script),
            "--v", str(n_videos),
            "--k", str(batch_size),
            "--min-k-size", str(mink),
            "--outfile", output_file,
            "--seed", str(seed),
            "--offline-first",  # Use cache if available
            "--out-indexing", "zero"  # Use 0-based indexing for consistency
        ]
        
        print(f"🚀 Running optimize_cover_flex.py: {' '.join(cmd[2:])}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)  # 10 minute timeout
        
        if result.returncode == 0 and os.path.exists(output_file):
            # Parse the output file - variable length lines
            batches = []
            with open(output_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Parse space or comma-separated integers
                        parts = line.replace(',', ' ').split()
                        batch = [int(x) for x in parts if x.isdigit()]
                        if len(batch) >= mink:  # Ensure minimum size constraint
                            batches.append(batch)
            
            if batches:
                print(f"✅ Created {len(batches)} flexible batches with sizes ranging from {min(len(b) for b in batches)} to {max(len(b) for b in batches)}")
                return batches
            else:
                raise RuntimeError("No valid batches generated by optimize_cover_flex.py")
        else:
            # Check for specific error conditions
            stderr_lower = result.stderr.lower()
            if any(phrase in stderr_lower for phrase in [
                "not available", "not found", "no such covering", 
                "could not parse", "404", "not cached", "cache miss"
            ]):
                raise RuntimeError(f"optimize_cover_flex.py failed: {result.stderr}")
            else:
                raise RuntimeError(f"optimize_cover_flex.py failed with return code {result.returncode}: {result.stderr}")
                
    finally:
        # Clean up temporary file
        if os.path.exists(output_file):
            os.unlink(output_file)

def auto_detect_stimuli(input_dir: str) -> int:
    """
    Auto-detect the number of video/audio files in a directory.
    
    Args:
        input_dir: Directory containing media files
        
    Returns:
        Number of media files found
        
         Example:
         >>> import multiarrangement as ma
         >>> n_stimuli = ma.auto_detect_stimuli("./videos")
         >>> batches = ma.create_batches(n_stimuli, 8)
    """
    import os
    
    # Supported file extensions
    video_extensions = ['.avi', '.mp4', '.mov', '.mkv', '.wmv']
    audio_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a']
    image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp']
    
    if not os.path.exists(input_dir):
        raise ValueError(f"Directory '{input_dir}' does not exist!")
    
    media_files = []
    for file in os.listdir(input_dir):
        ext = os.path.splitext(file)[1].lower()
        if ext in video_extensions or ext in audio_extensions or ext in image_extensions:
            media_files.append(file)
    
    return len(media_files)

def validate_batches(batches, n_videos: int):
    """
    Validate that batch configuration matches the number of videos.
    
    Args:
        batches: List of batches to validate
        n_videos: Expected number of videos
        
    Raises:
        ValueError: If validation fails
    """
    all_indices = set()
    for batch in batches:
        all_indices.update(batch)
    
    max_index = max(all_indices) if all_indices else -1
    n_unique_indices = len(all_indices)
    expected_max_index = n_videos - 1
    
    if max_index >= n_videos:
        raise ValueError(f"Batch indices go up to {max_index} but only {n_videos} videos expected! "
                        f"Indices should be 0-{expected_max_index}")
    
    if n_unique_indices != n_videos:
        missing_indices = set(range(n_videos)) - all_indices
        extra_indices = all_indices - set(range(n_videos))
        
        error_msg = f"Mismatch: {n_unique_indices} unique indices in batches vs {n_videos} videos expected"
        if missing_indices:
            error_msg += f"\nMissing indices: {sorted(missing_indices)}"
        if extra_indices:
            error_msg += f"\nExtra indices: {sorted(extra_indices)}"
        
        raise ValueError(error_msg)
    
    print(f"✅ Batch validation passed: {n_unique_indices} indices for {n_videos} videos")

def multiarrangement(
    input_dir: str,
    batches,
    output_dir: str,
    *,
    show_first_frames: bool = True,
    fullscreen: bool = True,
    language: str = "en",
    instructions = "default",
    # Set‑cover fusion controls (Ma.md alignment)
    setcover_weight_alpha: float = 2.0,
    setcover_weight_mode: str = 'max',
    rng_seed: int = None,
    use_inverse_mds: bool = False,
    inverse_mds_max_iter: int = 15,
    inverse_mds_step_c: float = 0.3,
    inverse_mds_tol: float = 1e-4,
    max_adjacent_overlap: Optional[int] = None,
    robust_method: Optional[str] = None,
    robust_winsor_high: float = 0.98,
    robust_huber_c: float = 0.9,
):
    """
    Run the multiarrangement experiment.
    
    Args:
        input_dir: Directory containing media files (videos/audio)
        batches: List of batches (from create_batches) or path to batch file
        output_dir: Directory to save results
        show_first_frames: Whether to show video frames (True) or ? emoji (False)
        fullscreen: Whether to run in fullscreen mode
        setcover_weight_mode: 'max' (per‑trial max‑norm), 'rms' (RMS‑matched), or 'k2012' (raw‑distance weights + RMS‑matched numerator)
        rng_seed: Optional integer RNG seed recorded in metadata and used for shuffles
    
    Returns:
        Results: convenience wrapper with matrix/labels and plotting helpers.
    
         Example:
         >>> import multiarrangement as ma
         >>> batches = ma.create_batches(42, 6)
         >>> result_file = ma.multiarrangement("./videos", batches, "./results")
    """
    from .experiment_runner import run_multiarrangement_experiment
    csv_path = run_multiarrangement_experiment(
        input_dir=input_dir,
        batches=batches,
        output_dir=output_dir,
        show_first_frames=show_first_frames,
        fullscreen=fullscreen,
        language=language,
        instructions=instructions,
        setcover_weight_mode=str(setcover_weight_mode),
        setcover_weight_alpha=float(setcover_weight_alpha),
        rng_seed=rng_seed,
        use_inverse_mds=bool(use_inverse_mds),
        inverse_mds_max_iter=int(inverse_mds_max_iter),
        inverse_mds_step_c=float(inverse_mds_step_c),
        inverse_mds_tol=float(inverse_mds_tol),
        max_adjacent_overlap=max_adjacent_overlap,
        robust_method=robust_method,
        robust_winsor_high=float(robust_winsor_high),
        robust_huber_c=float(robust_huber_c),
    )
    # Wrap results with a convenient visualization helper
    try:
        res = Results.from_csv(csv_path)
        res.meta.update({
            "mode": "set-cover",
            "input_dir": input_dir,
            "setcover_weight_alpha": float(setcover_weight_alpha),
            "setcover_weight_mode": str(setcover_weight_mode),
            "use_inverse_mds": bool(use_inverse_mds),
            "inverse_mds_max_iter": int(inverse_mds_max_iter),
            "inverse_mds_step_c": float(inverse_mds_step_c),
            "inverse_mds_tol": float(inverse_mds_tol),
            "max_adjacent_overlap": max_adjacent_overlap,
            "robust_method": robust_method,
            "robust_winsor_high": float(robust_winsor_high),
            "robust_huber_c": float(robust_huber_c),
        })
        return res
    except Exception:
        return csv_path

def demo():
    """
    Run a demo experiment with 15 videos, batch size 6, saving results to current directory.
    
    This function automatically:
    - Uses the 15videos directory that comes with the library
    - Creates batches with size 6
    - Saves results to the current directory
    
    Returns:
        Path to the saved distance matrix file
        
    Example:
        >>> import multiarrangement as ma
        >>> result_file = ma.demo()
    """
    import os
    
    print("🎬 Multiarrangement Demo - 15 videos, batch size 6")
    print("=" * 50)
    
    # Resolve demo media robustly (handles wheels, sdists, and data_files placement)
    from .utils.file_utils import resolve_packaged_dir
    try:
        input_dir = str(resolve_packaged_dir("15videos"))
    except FileNotFoundError:
        raise FileNotFoundError(
            "Demo media not found. Ensure the package was installed with demo media, "
            "or place a '15videos' folder next to your working directory."
        )
    
    # Auto-detect videos
    n_videos = auto_detect_stimuli(input_dir)
    print(f"✅ Found {n_videos} videos in '{input_dir}'")
    
    # Create batches with size 6
    print("🔧 Creating batches with size 6...")
    batches = create_batches(n_videos, 6)
    print(f"✅ Created {len(batches)} batches")
    
    # Validate batches
    validate_batches(batches, n_videos)
    
    # Set output directory to current directory
    output_dir = "."
    print(f"📁 Results will be saved to current directory: {os.path.abspath(output_dir)}")
    
    # Run the experiment
    print("\n🚀 Starting multiarrangement experiment...")
    print("   - Double-click videos to play them")
    print("   - Arrange videos by similarity in the circle")
    
    result_obj = multiarrangement(
        input_dir=input_dir,
        batches=batches,
        output_dir=output_dir,
        show_first_frames=True,  # Show grey screen instead of first frames
        fullscreen=True,
        instructions="default"
    )
    
    print(f"\n🎉 Demo completed successfully!")
    csv_path = getattr(result_obj, 'meta', {}).get('csv_path', '(see returned Results object)')
    print(f"📄 CSV path: {csv_path}")
    print("🖼️  Tip: call result.vis() to view the heatmap.")
    
    return result_obj

def demo_adaptive():
    """
    Run the adaptive (Lift-the-Weakest) demo with 15 videos.

    Behavior:
    - Uses the local "15videos" directory (must exist next to your working dir)
    - Runs the adaptive LTW experiment with friendly demo settings
      (lower evidence threshold and mid-sized subsets)
    - Saves results to the current directory

    Returns:
        None
    """
    import os

    print("🎬 Adaptive Multiarrangement Demo (LTW) - 15 videos")
    print("=" * 50)

    # Resolve demo media robustly
    from .utils.file_utils import resolve_packaged_dir
    input_dir = str(resolve_packaged_dir("15videos"))

    # Save to current directory
    output_dir = "."
    print(f"📁 Results will be saved to: {os.path.abspath(output_dir)}")

    # Friendlier demo defaults: slightly lower threshold, 4–6 item subsets, fullscreen UI
    multiarrangement_adaptive(
        input_dir=input_dir,
        output_dir=output_dir,
        fullscreen=True,
        evidence_threshold=0.35,
        min_subset_size=4,
        max_subset_size=6,
        use_inverse_mds=True,
    )

def multiarrangement_adaptive(
    input_dir: str,
    output_dir: str,
    participant_id: str = "participant",
    *,
    fullscreen: bool = True,
    language: str = "en",
    evidence_threshold: float = 0.5,
    utility_exponent: float = 10.0,
    time_limit_minutes: float = None,
    target_time_seconds: float = None,
    target_time_tolerance: float = 0.05,
    min_subset_size: int = 3,
    max_subset_size: int = None,
    use_inverse_mds: bool = False,
    inverse_mds_max_iter: int = 15,
    inverse_mds_step_c: float = 0.3,
    inverse_mds_tol: float = 1e-4,
    instructions = "default",
    # New policy options (safe defaults preserve current behavior)
    evidence_alpha: float = 2.0,
    unseen_boost: float = 0.0,
    recency_penalty: float = 0.0,
    recency_decay: float = 0.85,
    stress_weight: float = 0.0,
    max_jaccard: Optional[float] = None,
    overlap_penalty: float = 0.0,
    duration_cost_weight: float = 0.0,
    duration_cost_cap_per_item: float = None,
    robust_method: Optional[str] = None,
    robust_winsor_high: float = 0.98,
    robust_huber_c: float = 0.9,
    long_clip_threshold_seconds: float = None,
    min_long_clip_inclusion_rate: float = 0.0,
    long_clip_boost: float = 0.0,
    avoid_anchor_reuse: bool = False,
    cold_start_require_unseen_trials: int = 0,
    evidence_weight_mode: str = 'k2012',
    stop_on_utility: bool = False,
):
    """
    Run the adaptive lift-the-weakest multiarrangement experiment.

    Minimal usage:
        >>> import multiarrangement as ma
        >>> ma.multiarrangement_adaptive("./videos", output_dir="./results")
    """
    cfg = AdaptiveConfig(
        evidence_threshold=evidence_threshold,
        utility_exponent=utility_exponent,
        time_limit_seconds=(time_limit_minutes * 60.0) if time_limit_minutes else None,
        target_time_seconds=target_time_seconds if target_time_seconds is not None else None,
        target_time_tolerance=float(target_time_tolerance),
        min_subset_size=max(3, int(min_subset_size)),
        max_subset_size=int(max_subset_size) if max_subset_size is not None else None,
        use_inverse_mds=use_inverse_mds,
        inverse_mds_max_iter=inverse_mds_max_iter,
        inverse_mds_step_c=inverse_mds_step_c,
        inverse_mds_tol=inverse_mds_tol,
        evidence_alpha=evidence_alpha,
        unseen_boost=unseen_boost,
        recency_penalty=recency_penalty,
        recency_decay=recency_decay,
        stress_weight=stress_weight,
        max_jaccard=max_jaccard,
        overlap_penalty=overlap_penalty,
        duration_cost_weight=duration_cost_weight,
        duration_cost_cap_per_item=duration_cost_cap_per_item if duration_cost_cap_per_item is not None else None,
        robust_method=robust_method,
        robust_winsor_high=robust_winsor_high,
        robust_huber_c=robust_huber_c,
        long_clip_threshold_seconds=long_clip_threshold_seconds if long_clip_threshold_seconds is not None else None,
        min_long_clip_inclusion_rate=float(min_long_clip_inclusion_rate),
        long_clip_boost=float(long_clip_boost),
        avoid_anchor_reuse=avoid_anchor_reuse,
        cold_start_require_unseen_trials=int(cold_start_require_unseen_trials),
        evidence_weight_mode=evidence_weight_mode,
        stop_on_utility=stop_on_utility,
    )

    exp = AdaptiveMultiarrangementExperiment(
        input_directory=input_dir,
        participant_id=participant_id,
        output_directory=output_dir,
        config=cfg,
        language=language,
    )

    from .ui.fullscreen_interface import FullscreenInterface
    interface = FullscreenInterface(exp) if fullscreen else MultiarrangementInterface(exp)
    # Attach custom instructions if provided as a list; 'default' -> show built-ins; None -> skip
    if isinstance(instructions, list):
        interface.custom_instructions = instructions
    interface.run()
    # Return a Results object with the final RDM and labels
    try:
        res = Results(matrix=exp.D_est.astype(float), labels=list(exp.video_names), meta={
            "mode": "adaptive",
            "input_dir": input_dir,
            "participant_id": participant_id,
        })
        return res
    except Exception:
        return None

__all__ = [
    "MultiarrangementExperiment",
    "MultiarrangementInterface", 
    "VideoProcessor",
    "DataProcessor",
    "BatchGenerator",
    "create_batches",
    "auto_detect_stimuli",
    "validate_batches",
    "multiarrangement",
    "demo",
    "demo_audio",
    "demo_image",
    "demo_audio_adaptive",
    "demo_image_adaptive",
    "demo_adaptive",
    "multiarrangement_adaptive",
    "Results",
]


def _resolve_or_generate_15images() -> str:
    """Resolve a '15images' directory or generate from packaged 15videos.

    Returns a directory path containing 15 image files. If no 15images is
    bundled, it will extract first frames from the packaged 15videos into a
    temporary directory for demo use.
    """
    import os
    from .utils.file_utils import resolve_packaged_dir
    from pathlib import Path
    import tempfile
    import cv2

    try:
        # Prefer packaged images if present
        return str(resolve_packaged_dir("15images"))
    except FileNotFoundError:
        pass

    # Fallback: generate images from packaged 15videos
    try:
        vids = resolve_packaged_dir("15videos")
    except FileNotFoundError:
        raise FileNotFoundError(
            "Neither '15images' nor '15videos' found in the installed package. "
            "Please provide an images folder or install demos."
        )

    outdir = Path(tempfile.mkdtemp(prefix="ma_15images_"))
    print(f"🖼️ Generating demo images from first frames in: {vids}\n→ Output: {outdir}")
    count = 0
    for p in sorted(Path(vids).iterdir()):
        if p.suffix.lower() not in {'.avi', '.mp4', '.mov', '.mkv', '.wmv'}:
            continue
        cap = cv2.VideoCapture(str(p))
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            # Resize modestly to keep thumbnails reasonable
            h, w = frame.shape[:2]
            scale = min(480 / max(1,h), 640 / max(1,w))
            frame = cv2.resize(frame, (max(1,int(w*scale)), max(1,int(h*scale))))
            cv2.imwrite(str(outdir / f"img_{count:03d}.png"), frame)
            count += 1
        if count >= 15:
            break
    if count == 0:
        raise RuntimeError("Failed to generate images from demo videos.")
    return str(outdir)


def demo_audio():
    """Run an audio-only demo using packaged '15audios' (fallback: 'sample_audio')."""
    import os
    from .utils.file_utils import resolve_packaged_dir
    print("🔊 Multiarrangement Audio Demo - 15 items")
    try:
        input_dir = str(resolve_packaged_dir("15audios"))
    except FileNotFoundError:
        input_dir = str(resolve_packaged_dir("sample_audio"))
    n = auto_detect_stimuli(input_dir)
    batches = create_batches(n, 6)
    validate_batches(batches, n)
    print(f"📁 Results will be saved to current directory: {os.path.abspath('.')}")
    res = multiarrangement(
        input_dir=input_dir,
        batches=batches,
        output_dir=".",
        show_first_frames=True,
        fullscreen=True,
        language="en",
        instructions="default",
    )
    return res


def demo_image():
    """Run an image-only demo using '15images' or generated from '15videos'."""
    import os
    input_dir = _resolve_or_generate_15images()
    n = auto_detect_stimuli(input_dir)
    batches = create_batches(n, 6)
    validate_batches(batches, n)
    print(f"📁 Results will be saved to current directory: {os.path.abspath('.')}")
    res = multiarrangement(
        input_dir=input_dir,
        batches=batches,
        output_dir=".",
        show_first_frames=True,
        fullscreen=True,
        language="en",
        instructions="default",
    )
    return res


def demo_audio_adaptive():
    """Run the adaptive (LTW) demo with audio-only stimuli."""
    import os
    from .utils.file_utils import resolve_packaged_dir
    print("🔊 Adaptive Audio Demo - 15 items")
    try:
        input_dir = str(resolve_packaged_dir("15audios"))
    except FileNotFoundError:
        input_dir = str(resolve_packaged_dir("sample_audio"))
    print(f"📁 Results will be saved to current directory: {os.path.abspath('.')}")
    return multiarrangement_adaptive(
        input_dir=input_dir,
        output_dir=".",
        fullscreen=True,
        language="en",
        evidence_threshold=0.35,
        min_subset_size=4,
        max_subset_size=6,
        use_inverse_mds=True,
    )


def demo_image_adaptive():
    """Run the adaptive (LTW) demo with image-only stimuli."""
    import os
    input_dir = _resolve_or_generate_15images()
    print(f"📁 Results will be saved to current directory: {os.path.abspath('.')}")
    return multiarrangement_adaptive(
        input_dir=input_dir,
        output_dir=".",
        fullscreen=True,
        language="en",
        evidence_threshold=0.35,
        min_subset_size=4,
        max_subset_size=6,
        use_inverse_mds=True,
    )

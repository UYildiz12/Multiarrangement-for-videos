"""
File utilities for multiarrangement experiments.
"""

import os
import re
from pathlib import Path
from typing import List, Union, Optional
import site


def get_resource_path(filename: str) -> Path:
    """
    Get the path to a resource file, handling both development and installed package.
    
    Args:
        filename: Name of the resource file
        
    Returns:
        Path to the resource file
    """
    # Try relative to current file first (development)
    current_dir = Path(__file__).parent.parent
    resource_path = current_dir / "data" / filename
    
    if resource_path.exists():
        return resource_path
        
    # Try relative to current working directory
    cwd_path = Path.cwd() / filename
    if cwd_path.exists():
        return cwd_path
        
    # Try in the same directory as the main script
    script_dir = Path.cwd()
    script_path = script_dir / filename
    if script_path.exists():
        return script_path
        
    raise FileNotFoundError(f"Could not find resource file: {filename}")


def _iter_site_package_candidates(subdir: Optional[str] = None) -> List[Path]:
    """Yield candidate paths under site-packages that may contain our data.

    We search both global and user site-packages. If ``subdir`` is provided,
    we append it under the ``multiarrangement`` package directory.
    """
    candidates: List[Path] = []
    try:
        sp = list(site.getsitepackages())
    except Exception:
        sp = []
    try:
        usp = site.getusersitepackages()
        if usp:
            sp.append(usp)
    except Exception:
        pass
    for base in sp:
        p = Path(base) / "multiarrangement"
        if subdir:
            p = p / subdir
        candidates.append(p)
    return candidates


def resolve_packaged_dir(name: str) -> Path:
    """Resolve a packaged data directory robustly.

    Search order:
    - Inside the installed package: ``<pkg>/name``
    - Current working directory: ``./name``
    - Site-packages fallbacks: ``<site>/multiarrangement/name``

    Returns the first existing directory with at least one file.
    Raises FileNotFoundError if not found.
    """
    # 1) Package directory
    pkg_root = Path(__file__).parent.parent  # multiarrangement/
    candidates: List[Path] = [pkg_root / name, Path.cwd() / name]
    candidates.extend(_iter_site_package_candidates(subdir=name))

    for p in candidates:
        try:
            if p.exists() and any(p.iterdir()):
                return p
        except Exception:
            # Ignore permission or filesystem errors
            continue

    raise FileNotFoundError(f"Could not locate packaged directory '{name}'. Searched: "
                            f"{', '.join(str(c) for c in candidates)}")


def resolve_packaged_file(subdir: str, filename: str) -> Path:
    """Resolve a file within a packaged data subdirectory.

    Tries the same locations as ``resolve_packaged_dir``. Returns a Path that exists.
    Raises FileNotFoundError if not found.
    """
    # Assemble candidate directories and check for the file
    dirs = [
        Path(__file__).parent.parent / subdir,
        Path.cwd() / subdir,
        *_iter_site_package_candidates(subdir=subdir),
    ]
    for d in dirs:
        p = d / filename
        if p.exists():
            return p
    raise FileNotFoundError(f"Could not locate '{filename}' under '{subdir}'. Searched: "
                            f"{', '.join(str(d) for d in dirs)}")


def load_batches(batch_file: Union[str, Path]) -> List[List[int]]:
    """
    Load batch configuration from a file.
    
    Supports various formats:
    - Comma-separated values: 1,2,3,4
    - Bracketed lists: [1,2,3,4]
    - Parenthesized lists: (1,2,3,4)
    
    Args:
        batch_file: Path to the batch configuration file
        
    Returns:
        List of batches, where each batch is a list of video indices
    """
    batch_file = Path(batch_file)
    
    if not batch_file.exists():
        raise FileNotFoundError(f"Batch file not found: {batch_file}")
        
    batches = []
    
    with open(batch_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            try:
                # Extract numbers using regex (handles various formats)
                numbers = re.findall(r'-?\d+', line)
                if numbers:
                    batch = [int(num) for num in numbers]
                    batches.append(batch)
                    
            except ValueError as e:
                raise ValueError(f"Error parsing batch file line {line_num}: {line}") from e
                
    if not batches:
        raise ValueError(f"No valid batches found in {batch_file}")
        
    return batches


def ensure_directory_exists(directory: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Path to the directory
        
    Returns:
        Path object for the directory
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_video_files(directory: Union[str, Path], extensions: List[str] = None) -> List[Path]:
    """
    Get all video files in a directory.
    
    Args:
        directory: Path to the directory containing videos
        extensions: List of file extensions to include (default: common video formats)
        
    Returns:
        List of Path objects for video files
    """
    if extensions is None:
        # Broaden default support to include common containers/codecs often seen in datasets
        extensions = [
            '.avi', '.mp4', '.mov', '.mkv', '.wmv', '.flv', '.webm',
            '.m4v', '.mpg', '.mpeg', '.ts', '.m2ts', '.mts', '.3gp', '.ogv'
        ]
        
    directory = Path(directory)
    
    if not directory.exists():
        raise FileNotFoundError(f"Video directory not found: {directory}")
        
    # Normalize extension set to lowercase to match case-insensitively
    ext_set = {e.lower() for e in extensions}

    # Iterate entries once and filter by suffix to avoid duplicates on case-insensitive filesystems
    seen: set = set()
    video_files: List[Path] = []
    for p in directory.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() in ext_set:
            # Use lowercase absolute path as a stable dedup key
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            video_files.append(p)

    # Sort by name for stable ordering
    return sorted(video_files, key=lambda x: x.name.lower())


def validate_batch_configuration(batches: List[List[int]], num_videos: int) -> None:
    """
    Validate that batch configuration is compatible with available videos.
    
    Args:
        batches: List of batches (each batch is a list of video indices)
        num_videos: Total number of available videos
        
    Raises:
        ValueError: If batch configuration is invalid
    """
    for batch_idx, batch in enumerate(batches):
        # Check for empty batches
        if not batch:
            raise ValueError(f"Batch {batch_idx} is empty")
            
        # Check for duplicate indices within batch
        if len(batch) != len(set(batch)):
            raise ValueError(f"Batch {batch_idx} contains duplicate indices: {batch}")
            
        # Check for out-of-range indices
        for video_idx in batch:
            if video_idx < 0 or video_idx >= num_videos:
                raise ValueError(
                    f"Batch {batch_idx} contains invalid index {video_idx}. "
                    f"Valid range is 0-{num_videos-1}"
                )


def create_default_batch_file(num_videos: int, batch_size: int, output_file: Union[str, Path]) -> None:
    """
    Create a simple sequential batch file for testing purposes.
    
    Args:
        num_videos: Total number of videos
        batch_size: Number of videos per batch
        output_file: Path to save the batch file
    """
    output_file = Path(output_file)
    
    batches = []
    for i in range(0, num_videos, batch_size):
        batch = list(range(i, min(i + batch_size, num_videos)))
        batches.append(batch)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Simple sequential batches for {num_videos} videos\n")
        f.write(f"# Batch size: {batch_size}\n")
        f.write(f"# Generated automatically\n\n")
        
        for batch in batches:
            f.write(','.join(map(str, batch)) + '\n')
            
    print(f"Created batch file: {output_file}")

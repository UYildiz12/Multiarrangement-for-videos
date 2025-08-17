from __future__ import annotations
from pathlib import Path
from typing import List, Tuple

__all__ = ["cache_path", "read_blocks_file", "save_blocks_file", "get_seed_blocks"]

def cache_path(cache_dir: Path, v: int, k: int) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"v{v}_k{k}_t2.txt"

def read_blocks_file(path: Path, v: int, k: int) -> List[Tuple[int,...]]:
    blocks: List[Tuple[int,...]] = []
    if not path.exists(): return blocks
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip().replace(",", " ")
            if not ln or ln.startswith("#"): continue
            nums = [int(x) for x in ln.split()]
            if len(nums) != k: continue
            blocks.append(tuple(sorted(nums)))
    if not blocks: return []
    zero_based = any(0 in b for b in blocks)
    if not zero_based:
        blocks = [tuple(x-1 for x in b) for b in blocks]
    for b in blocks:
        if any(x < 0 or x >= v for x in b):
            raise ValueError(f"{path}: item out of range for v={v}.")
    return blocks

def save_blocks_file(path: Path, blocks: List[Tuple[int,...]], indexing: str = "zero") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for b in blocks:
            if indexing == "one":
                f.write(" ".join(str(x+1) for x in b) + "\n")
            else:
                f.write(" ".join(str(x) for x in b) + "\n")

def get_seed_blocks(v: int, k: int, cache_dir: Path, offline_first: bool, offline_only: bool,
                    fetcher) -> List[Tuple[int,...]]:
    p = cache_path(cache_dir, v, k)
    if offline_first or offline_only:
        blocks = read_blocks_file(p, v, k)
        if blocks:
            print(f"Loaded seed from cache: {p} (blocks={len(blocks)})")
            return blocks
        if offline_only:
            raise RuntimeError(f"Cache miss and offline-only enabled. Expected: {p}")
    print(f"Cache miss for (v={v},k={k}). Fetching from LJCR…")
    blocks = fetcher(v, k)
    save_blocks_file(p, blocks, indexing="zero")
    print(f"Saved LJCR seed to cache: {p}")
    return blocks

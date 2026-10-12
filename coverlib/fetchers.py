from __future__ import annotations
import html, re, urllib.request
from typing import List, Tuple

LJCR_URL = "https://ljcr.dmgordon.org/cover/show_cover.php?v={v}&k={k}&t=2"
_INT_RE = re.compile(r"-?\d+")

__all__ = ["fetch_ljcr_cover"]


def _valid_block(nums: List[int], v: int, k: int) -> bool:
    return (
        len(nums) == k
        and len(set(nums)) == k
        and all(1 <= item <= v for item in nums)
    )


def fetch_ljcr_cover(v: int, k: int) -> List[Tuple[int,...]]:
    url = LJCR_URL.format(v=v, k=k)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch LJCR page: {e} | URL: {url}")

    text = html.unescape(data)
    blocks: List[Tuple[int,...]] = []

    # Strategy 1: parse <pre>/<code>
    for tag in ("pre","code"):
        for m in re.finditer(fr"(?is)<{tag}[^>]*>(.*?)</{tag}>", text):
            for line in m.group(1).splitlines():
                nums = [int(x) for x in _INT_RE.findall(line)]
                if _valid_block(nums, v, k):
                    blk = tuple(sorted(x-1 for x in nums))
                    blocks.append(blk)
        if blocks: return blocks

    # Strategy 2: per-line fallback
    for line in text.splitlines():
        nums = [int(x) for x in _INT_RE.findall(line)]
        if _valid_block(nums, v, k):
            blk = tuple(sorted(x-1 for x in nums))
            blocks.append(blk)
    if blocks: return blocks

    # Strategy 3: collect long run after first block-ish line
    allints: List[int] = []
    seen_first = False
    for line in text.splitlines():
        nums = [int(x) for x in _INT_RE.findall(line)]
        if not nums: continue
        if not seen_first and _valid_block(nums, v, k):
            seen_first = True; allints.extend(nums)
        elif seen_first:
            allints.extend(nums)
    if allints:
        for i in range(0, len(allints), k):
            chunk = allints[i:i+k]
            if not _valid_block(chunk, v, k):
                continue
            blk = tuple(sorted(x-1 for x in chunk))
            blocks.append(blk)
    if not blocks:
        raise RuntimeError(f"Could not parse any {k}-tuples from LJCR page for (v={v},k={k}). URL: {url}")

    # sanity: uniform k
    ks = {len(b) for b in blocks}
    if len(ks) != 1 or list(ks)[0] != k:
        raise RuntimeError(f"Parsed blocks have inconsistent k: {ks}")
    return blocks

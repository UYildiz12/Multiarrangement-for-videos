"""Reproducible discovery, certification, and selection of schedule frontiers."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .cache import read_blocks_file
from .certificates import (
    ScheduleCertificate,
    balanced_sort_key,
    certify_schedule,
    compact_sort_key,
    pareto_frontier,
)
from .constructions import structured_cover_candidates


Block = Tuple[int, ...]
_BALANCED_NAME = re.compile(r"v(\d+)_k(\d+)_b\d+(?:_[0-9a-f]+)?\.txt$")
_LJCR_NAME = re.compile(r"v(\d+)_k(\d+)_t2\.txt$")
INDEX_VERSION = 1


@dataclass(frozen=True)
class FrontierCandidate:
    blocks: Tuple[Block, ...]
    certificate: ScheduleCertificate
    source: str
    path: Optional[Path] = None


def _candidate_from_file(
    path: Path,
    v: int,
    k: int,
    *,
    source: str,
) -> Optional[FrontierCandidate]:
    try:
        blocks = tuple(read_blocks_file(path, v, k))
        certificate = certify_schedule(v, k, blocks, source=source)
    except Exception:
        return None
    if not certificate.complete:
        return None
    return FrontierCandidate(blocks, certificate, source, path)


def discover_repository_candidates(
    repo_root: str | Path,
    *,
    include_structured: bool = True,
    include_generated: bool = True,
    extra_dirs: Sequence[str | Path] = (),
) -> Dict[Tuple[int, int], List[FrontierCandidate]]:
    """Discover old caches, prior generated candidates, and constructions."""
    root = Path(repo_root).resolve()
    package_dir = root / "multiarrangement"
    grouped: Dict[Tuple[int, int], List[FrontierCandidate]] = {}

    file_specs = [
        (package_dir / "balanced_cache", _BALANCED_NAME, "balanced_cache"),
        (package_dir / "ljcr_cache", _LJCR_NAME, "ljcr_cache"),
    ]
    if include_generated:
        file_specs.extend(
            [
                (
                    package_dir / "frontier_candidates",
                    _BALANCED_NAME,
                    "portfolio_search",
                ),
                (package_dir / "frontier_cache", _BALANCED_NAME, "frontier_cache"),
                (root / "orbit_out", _BALANCED_NAME, "orbit_search"),
            ]
        )
    file_specs.extend(
        (Path(directory), _BALANCED_NAME, "external_candidate")
        for directory in extra_dirs
    )
    for directory, pattern, source in file_specs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("v*_k*.txt")):
            match = pattern.match(path.name)
            if not match:
                continue
            v, k = (int(value) for value in match.groups())
            candidate = _candidate_from_file(path, v, k, source=source)
            if candidate is not None:
                grouped.setdefault((v, k), []).append(candidate)

    if include_structured:
        keys = set(grouped)
        for k in range(3, 11):
            for v in range(max(5, k + 1), 101):
                if structured_cover_candidates(v, k):
                    keys.add((v, k))
        for v, k in sorted(keys):
            for constructed in structured_cover_candidates(v, k):
                certificate = certify_schedule(
                    v,
                    k,
                    constructed.blocks,
                    source=constructed.source,
                )
                grouped.setdefault((v, k), []).append(
                    FrontierCandidate(
                        tuple(constructed.blocks),
                        certificate,
                        constructed.source,
                    )
                )
    return grouped


def _deduplicate_candidates(
    candidates: Iterable[FrontierCandidate],
) -> List[FrontierCandidate]:
    by_hash: Dict[str, FrontierCandidate] = {}
    source_priority = {
        "exact_design": 0,
        "one_point_extension": 1,
        "one_point_truncation": 2,
        "frontier_cache": 3,
        "balanced_cache": 4,
        "ljcr_cache": 5,
    }
    for candidate in candidates:
        schedule_hash = candidate.certificate.schedule_hash
        incumbent = by_hash.get(schedule_hash)
        if incumbent is None:
            by_hash[schedule_hash] = candidate
            continue
        if source_priority.get(candidate.source, 99) < source_priority.get(
            incumbent.source,
            99,
        ):
            by_hash[schedule_hash] = candidate
    return list(by_hash.values())


def candidate_frontier(
    candidates: Iterable[FrontierCandidate],
) -> Tuple[FrontierCandidate, ...]:
    """Return the nondominated, hash-deduplicated candidate frontier."""
    unique = _deduplicate_candidates(candidates)
    certificates = pareto_frontier(candidate.certificate for candidate in unique)
    frontier_hashes = {certificate.schedule_hash for certificate in certificates}
    representatives: Dict[Tuple[object, ...], FrontierCandidate] = {}
    for candidate in unique:
        if candidate.certificate.schedule_hash not in frontier_hashes:
            continue
        quality = (
            candidate.certificate.b,
            candidate.certificate.concurrence_profile,
        )
        incumbent = representatives.get(quality)
        if incumbent is None or (
            candidate.certificate.item_deviation_profile,
            candidate.certificate.schedule_hash,
        ) < (
            incumbent.certificate.item_deviation_profile,
            incumbent.certificate.schedule_hash,
        ):
            representatives[quality] = candidate
    return tuple(
        sorted(
            representatives.values(),
            key=lambda candidate: (
                candidate.certificate.b,
                candidate.certificate.concurrence_profile,
                candidate.certificate.item_deviation_profile,
                candidate.certificate.schedule_hash,
            ),
        )
    )


def _write_blocks(path: Path, blocks: Sequence[Sequence[int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        " ".join(str(int(item)) for item in sorted(block)) + "\n"
        for block in blocks
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def rebuild_frontier_cache(
    repo_root: str | Path,
    *,
    extra_dirs: Sequence[str | Path] = (),
) -> dict:
    """Regenerate the manifest without deleting any prior schedule artifact."""
    root = Path(repo_root).resolve()
    package_dir = root / "multiarrangement"
    output_dir = package_dir / "frontier_cache"
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped = discover_repository_candidates(root, extra_dirs=extra_dirs)
    manifest_entries: Dict[str, List[dict]] = {}

    for (v, k), candidates in sorted(grouped.items()):
        entries = []
        for candidate in candidate_frontier(candidates):
            path = candidate.path
            if path is None or candidate.source in {
                "portfolio_search",
                "orbit_search",
                "external_candidate",
            }:
                filename = (
                    f"v{v}_k{k}_b{candidate.certificate.b}_"
                    f"{candidate.certificate.schedule_hash[:12]}.txt"
                )
                path = output_dir / filename
                _write_blocks(path, candidate.blocks)
            try:
                relative_path = path.resolve().relative_to(package_dir.resolve())
            except ValueError:
                filename = (
                    f"v{v}_k{k}_b{candidate.certificate.b}_"
                    f"{candidate.certificate.schedule_hash[:12]}.txt"
                )
                copied = output_dir / filename
                _write_blocks(copied, candidate.blocks)
                relative_path = copied.relative_to(package_dir)
            record = candidate.certificate.to_dict()
            record.update(
                {
                    "source": candidate.source,
                    "path": relative_path.as_posix(),
                }
            )
            entries.append(record)
        if entries:
            manifest_entries[f"{v},{k}"] = entries

    manifest = {
        "version": INDEX_VERSION,
        "generated_by": "coverlib.frontier",
        "parameter_pairs": len(manifest_entries),
        "frontier_points": sum(len(entries) for entries in manifest_entries.values()),
        "entries": manifest_entries,
    }
    index_path = output_dir / "index.json"
    index_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def audit_repository_improvements(repo_root: str | Path) -> dict:
    """Compare the full portfolio with the untouched historical caches."""
    baseline = discover_repository_candidates(
        repo_root,
        include_structured=False,
        include_generated=False,
    )
    current = discover_repository_candidates(repo_root)
    details: List[dict] = []
    compact_wins = 0
    balanced_wins = 0
    union_wins = 0

    for v, k in sorted(baseline):
        baseline_candidates = baseline[(v, k)]
        current_candidates = current.get((v, k), baseline_candidates)
        old_compact = min(
            baseline_candidates,
            key=lambda candidate: compact_sort_key(v, k, candidate.blocks),
        )
        old_balanced = min(
            baseline_candidates,
            key=lambda candidate: balanced_sort_key(v, k, candidate.blocks),
        )
        new_compact = min(
            current_candidates,
            key=lambda candidate: compact_sort_key(v, k, candidate.blocks),
        )
        new_balanced = min(
            current_candidates,
            key=lambda candidate: balanced_sort_key(v, k, candidate.blocks),
        )
        compact_improved = compact_sort_key(
            v,
            k,
            new_compact.blocks,
        ) < compact_sort_key(v, k, old_compact.blocks)
        balanced_improved = balanced_sort_key(
            v,
            k,
            new_balanced.blocks,
        ) < balanced_sort_key(v, k, old_balanced.blocks)
        compact_wins += int(compact_improved)
        balanced_wins += int(balanced_improved)
        union_wins += int(compact_improved or balanced_improved)
        if compact_improved or balanced_improved:
            details.append(
                {
                    "v": v,
                    "k": k,
                    "compact_improved": compact_improved,
                    "balanced_improved": balanced_improved,
                    "old_compact": old_compact.certificate.to_dict(),
                    "new_compact": new_compact.certificate.to_dict(),
                    "new_compact_source": new_compact.source,
                    "old_balanced": old_balanced.certificate.to_dict(),
                    "new_balanced": new_balanced.certificate.to_dict(),
                    "new_balanced_source": new_balanced.source,
                }
            )
    return {
        "version": 1,
        "baseline_parameter_pairs": len(baseline),
        "current_parameter_pairs": len(current),
        "compact_improved_pairs": compact_wins,
        "balanced_improved_pairs": balanced_wins,
        "improved_in_either_mode": union_wins,
        "details": details,
    }


def load_frontier_manifest(package_dir: str | Path) -> dict:
    path = Path(package_dir) / "frontier_cache" / "index.json"
    if not path.exists():
        return {"version": INDEX_VERSION, "entries": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != INDEX_VERSION:
        raise ValueError(f"unsupported frontier index version: {data.get('version')}")
    return data


def load_frontier_candidates(
    v: int,
    k: int,
    *,
    package_dir: str | Path,
    max_blocks: Optional[int] = None,
) -> List[FrontierCandidate]:
    package = Path(package_dir)
    manifest = load_frontier_manifest(package)
    candidates: List[FrontierCandidate] = []
    for record in manifest.get("entries", {}).get(f"{v},{k}", []):
        if max_blocks is not None and int(record["b"]) > max_blocks:
            continue
        path = package / record["path"]
        candidate = _candidate_from_file(
            path,
            v,
            k,
            source=str(record.get("source", "frontier_cache")),
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def select_frontier_cover(
    v: int,
    k: int,
    *,
    package_dir: str | Path,
    mode: str,
    max_blocks: Optional[int] = None,
) -> Optional[FrontierCandidate]:
    candidates = load_frontier_candidates(
        v,
        k,
        package_dir=package_dir,
        max_blocks=max_blocks,
    )
    if not candidates:
        return None
    if mode == "compact":
        return min(candidates, key=lambda candidate: compact_sort_key(v, k, candidate.blocks))
    if mode == "balanced":
        return min(candidates, key=lambda candidate: balanced_sort_key(v, k, candidate.blocks))
    raise ValueError("mode must be 'compact' or 'balanced'")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    rebuild = subparsers.add_parser("rebuild", help="rebuild the repository frontier")
    rebuild.add_argument("--repo-root", default=".")
    rebuild.add_argument("--extra-dir", action="append", default=[])
    audit = subparsers.add_parser("audit", help="compare portfolio with historical caches")
    audit.add_argument("--repo-root", default=".")
    audit.add_argument("--output")
    args = parser.parse_args(argv)
    if args.command == "rebuild":
        manifest = rebuild_frontier_cache(
            args.repo_root,
            extra_dirs=args.extra_dir,
        )
        print(
            f"frontier: {manifest['parameter_pairs']} parameter pairs, "
            f"{manifest['frontier_points']} points"
        )
        return 0
    if args.command == "audit":
        report = audit_repository_improvements(args.repo_root)
        if args.output:
            Path(args.output).write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        print(
            f"audit: compact={report['compact_improved_pairs']}, "
            f"balanced={report['balanced_improved_pairs']}, "
            f"either={report['improved_in_either_mode']}"
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

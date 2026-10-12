from __future__ import annotations

import json

from coverlib.certificates import balanced_sort_key, certify_schedule
from coverlib.frontier import (
    audit_repository_improvements,
    candidate_frontier,
    discover_repository_candidates,
    load_frontier_candidates,
    select_frontier_cover,
)


FANO = (
    (0, 1, 2),
    (0, 3, 4),
    (0, 5, 6),
    (1, 3, 5),
    (1, 4, 6),
    (2, 3, 6),
    (2, 4, 5),
)


def _write_schedule(path, blocks):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(" ".join(map(str, block)) + "\n" for block in blocks),
        encoding="utf-8",
    )


def test_discovery_preserves_existing_schedule_and_deduplicates(tmp_path):
    path = tmp_path / "multiarrangement" / "ljcr_cache" / "v7_k3_t2.txt"
    _write_schedule(path, FANO)

    grouped = discover_repository_candidates(tmp_path, include_structured=False)
    frontier = candidate_frontier(grouped[(7, 3)])

    assert len(frontier) == 1
    assert frontier[0].source == "ljcr_cache"
    assert frontier[0].certificate.complete


def test_manifest_selection_obeys_compact_and_balanced_objectives(tmp_path):
    package = tmp_path / "multiarrangement"
    compact_path = package / "frontier_cache" / "v6_k3_b7_compact.txt"
    balanced_path = package / "frontier_cache" / "v6_k3_b8_balanced.txt"
    compact = (
        (0, 2, 5), (1, 3, 4), (0, 1, 3), (1, 2, 3),
        (2, 4, 5), (1, 3, 5), (0, 3, 4),
    )
    balanced = (
        (0, 1, 2), (0, 3, 4), (0, 4, 5), (1, 3, 5),
        (1, 4, 5), (2, 3, 4), (2, 3, 5), (1, 2, 5),
    )
    _write_schedule(compact_path, compact)
    _write_schedule(balanced_path, balanced)
    entries = []
    for path, blocks in ((compact_path, compact), (balanced_path, balanced)):
        record = certify_schedule(6, 3, blocks, source="test").to_dict()
        record.update({"source": "test", "path": path.relative_to(package).as_posix()})
        entries.append(record)
    index = {
        "version": 1,
        "entries": {"6,3": entries},
    }
    (package / "frontier_cache" / "index.json").write_text(
        json.dumps(index),
        encoding="utf-8",
    )

    loaded = load_frontier_candidates(6, 3, package_dir=package)
    assert len(loaded) == 2
    compact_choice = select_frontier_cover(6, 3, package_dir=package, mode="compact")
    balanced_choice = select_frontier_cover(6, 3, package_dir=package, mode="balanced")
    assert compact_choice is not None
    assert balanced_choice is not None
    assert compact_choice.certificate.b == 7
    assert balanced_sort_key(6, 3, balanced_choice.blocks) <= balanced_sort_key(
        6,
        3,
        compact_choice.blocks,
    )


def test_audit_compares_generated_portfolio_with_historical_cache(tmp_path):
    old = (
        (0, 2, 5), (1, 3, 4), (0, 1, 3), (1, 2, 3),
        (2, 4, 5), (1, 3, 5), (0, 3, 4),
    )
    improved = (
        (0, 1, 3), (0, 1, 4), (0, 2, 5), (0, 3, 4),
        (1, 2, 3), (1, 3, 5), (2, 4, 5),
    )
    _write_schedule(
        tmp_path / "multiarrangement" / "ljcr_cache" / "v6_k3_t2.txt",
        old,
    )
    certificate = certify_schedule(6, 3, improved)
    _write_schedule(
        tmp_path / "multiarrangement" / "frontier_candidates"
        / f"v6_k3_b7_{certificate.schedule_hash[:12]}.txt",
        improved,
    )

    report = audit_repository_improvements(tmp_path)

    assert report["baseline_parameter_pairs"] == 1
    assert report["compact_improved_pairs"] == 1
    assert report["balanced_improved_pairs"] == 1
    assert report["improved_in_either_mode"] == 1

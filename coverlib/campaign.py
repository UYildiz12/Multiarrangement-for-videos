"""Bounded, resumable schedule-portfolio improvement campaigns.

Every candidate starts from the best existing certified schedule.  Search
stages may fail or time out without making a mathematical nonexistence claim;
only independently certified strict improvements are written.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .balanced import improve_pair_balance
from .certificates import (
    ScheduleCertificate,
    balanced_sort_key,
    certify_schedule,
    ideal_concurrence_profile,
)
from .frontier import candidate_frontier, discover_repository_candidates
from .residual import exact_neighborhood_repair
from .refinement import improve_item_balance
from .symmetry import search_symmetry_candidates


Block = Tuple[int, ...]
METHODS = ("local", "residual", "symmetry", "items")


@dataclass(frozen=True)
class CampaignCase:
    v: int
    k: int
    blocks: Tuple[Block, ...]
    source: str
    certificate: ScheduleCertificate

    @property
    def ideal(self) -> Tuple[int, ...]:
        return ideal_concurrence_profile(self.v, self.k, len(self.blocks))

    @property
    def lambda_gap(self) -> int:
        return self.certificate.lambda_max - self.ideal[0]


def rank_campaign_cases(
    repo_root: str | Path,
    *,
    include_ideal: bool = False,
) -> List[CampaignCase]:
    """Rank best-existing cases by certified distance from ideal balance."""
    grouped = discover_repository_candidates(repo_root)
    cases: List[CampaignCase] = []
    for (v, k), candidates in grouped.items():
        frontier = candidate_frontier(candidates)
        if not frontier:
            continue
        incumbent = min(
            frontier,
            key=lambda candidate: balanced_sort_key(v, k, candidate.blocks),
        )
        case = CampaignCase(
            v=v,
            k=k,
            blocks=incumbent.blocks,
            source=incumbent.source,
            certificate=incumbent.certificate,
        )
        if (include_ideal or case.certificate.concurrence_profile != case.ideal
                or case.certificate.item_range > 1):
            cases.append(case)
    return sorted(
        cases,
        key=lambda case: (
            -case.lambda_gap,
            -case.certificate.lambda_max,
            -case.v,
            -case.k,
            case.certificate.b,
        ),
    )


def _write_candidate(
    directory: Path,
    v: int,
    k: int,
    blocks: Sequence[Sequence[int]],
    certificate: ScheduleCertificate,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (
        f"v{v}_k{k}_b{len(blocks)}_{certificate.schedule_hash[:12]}.txt"
    )
    if not path.exists():
        path.write_text(
            "".join(
                " ".join(str(int(item)) for item in sorted(block)) + "\n"
                for block in blocks
            ),
            encoding="utf-8",
            newline="\n",
        )
    return path


def _candidate_record(
    method: str,
    source: str,
    before: ScheduleCertificate,
    after: ScheduleCertificate,
    path: Optional[Path],
    elapsed_seconds: float,
) -> dict:
    return {
        "method": method,
        "source": source,
        "strict_improvement": True,
        "before": before.to_dict(),
        "after": after.to_dict(),
        "path": str(path) if path is not None else None,
        "elapsed_seconds": round(elapsed_seconds, 6),
    }


def improve_case(
    case: CampaignCase,
    *,
    methods: Sequence[str] = METHODS,
    seconds_per_method: float = 1.0,
    seed: int = 12345,
    output_dir: Optional[str | Path] = None,
) -> Tuple[CampaignCase, List[dict]]:
    """Apply selected bounded stages and retain only exact-objective wins."""
    unknown = set(methods).difference(METHODS)
    if unknown:
        raise ValueError(f"unknown campaign methods: {sorted(unknown)}")
    current = case
    wins: List[dict] = []
    directory = Path(output_dir) if output_dir is not None else None

    def consider(
        method: str,
        source: str,
        raw_blocks: Sequence[Sequence[int]],
        started: float,
    ) -> None:
        nonlocal current
        candidate_blocks = tuple(
            sorted(tuple(sorted(int(item) for item in block)) for block in raw_blocks)
        )
        try:
            certificate = certify_schedule(
                case.v,
                case.k,
                candidate_blocks,
                source=source,
            )
        except Exception:
            return
        if not certificate.complete:
            return
        if balanced_sort_key(case.v, case.k, candidate_blocks) >= balanced_sort_key(
            case.v,
            case.k,
            current.blocks,
        ):
            return
        path = (
            _write_candidate(
                directory,
                case.v,
                case.k,
                candidate_blocks,
                certificate,
            )
            if directory is not None
            else None
        )
        wins.append(
            _candidate_record(
                method,
                source,
                current.certificate,
                certificate,
                path,
                time.perf_counter() - started,
            )
        )
        current = CampaignCase(
            case.v,
            case.k,
            candidate_blocks,
            source,
            certificate,
        )

    if "local" in methods:
        started = time.perf_counter()
        target = max(1, current.certificate.lambda_max - 1)
        candidate = improve_pair_balance(
            case.v,
            case.k,
            current.blocks,
            seed=seed,
            target_lmax=target,
            attempts=1,
            iterations=max(100_000, min(2_000_000, case.v * 20_000)),
            seconds_per_attempt=max(0.05, seconds_per_method),
        )
        consider("local", "bounded_swap_search", candidate, started)

    if "residual" in methods and current.certificate.lambda_max > current.ideal[0]:
        started = time.perf_counter()
        repair = exact_neighborhood_repair(
            case.v,
            case.k,
            current.blocks,
            max_removed_blocks=4,
            removal_sets_per_size=24,
            time_limit_seconds=max(0.05, seconds_per_method),
            seed=seed + 104729,
        )
        if repair is not None:
            consider(
                "residual",
                f"exact_residual_lambda_{repair.target_lambda_max}",
                repair.blocks,
                started,
            )

    if "symmetry" in methods and current.certificate.concurrence_profile != current.ideal:
        started = time.perf_counter()
        candidates = search_symmetry_candidates(
            case.v,
            case.k,
            max_blocks=len(current.blocks),
            incumbent_blocks=[list(block) for block in current.blocks],
            budget_seconds=max(0.05, seconds_per_method),
            seed=seed + 130363,
            max_plans=8,
        )
        for candidate in candidates:
            consider("symmetry", candidate.source, candidate.blocks, started)

    if "items" in methods:
        started = time.perf_counter()
        candidate = improve_item_balance(case.v, case.k, current.blocks)
        consider("items", "pair_histogram_preserving_item_trades", candidate, started)

    return current, wins


def run_campaign(
    repo_root: str | Path,
    *,
    methods: Sequence[str] = METHODS,
    seconds_per_method: float = 1.0,
    start_index: int = 0,
    max_cases: Optional[int] = None,
    seed: int = 12345,
    report_path: Optional[str | Path] = None,
) -> dict:
    """Run a deterministic slice so long campaigns are resumable."""
    root = Path(repo_root).resolve()
    cases = rank_campaign_cases(root)
    stop = len(cases) if max_cases is None else start_index + max(0, max_cases)
    selected = cases[max(0, start_index) : stop]
    output_dir = root / "multiarrangement" / "frontier_candidates"
    records: List[dict] = []
    win_cases = 0
    stage_wins = 0
    started = time.perf_counter()

    for offset, case in enumerate(selected):
        improved, wins = improve_case(
            case,
            methods=methods,
            seconds_per_method=seconds_per_method,
            seed=seed + (start_index + offset) * 1009 + case.v * 31 + case.k,
            output_dir=output_dir,
        )
        if wins:
            win_cases += 1
            stage_wins += len(wins)
        records.append(
            {
                "rank": start_index + offset,
                "v": case.v,
                "k": case.k,
                "b": case.certificate.b,
                "source": case.source,
                "before_hash": case.certificate.schedule_hash,
                "after_hash": improved.certificate.schedule_hash,
                "before_lambda_max": case.certificate.lambda_max,
                "after_lambda_max": improved.certificate.lambda_max,
                "wins": wins,
            }
        )
        print(
            f"[{start_index + offset + 1}/{len(cases)}] "
            f"v={case.v} k={case.k} b={case.certificate.b}: "
            f"{len(wins)} win(s), lambda "
            f"{case.certificate.lambda_max}->{improved.certificate.lambda_max}",
            flush=True,
        )

    report = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "methods": list(methods),
        "seconds_per_method": seconds_per_method,
        "start_index": start_index,
        "selected_cases": len(selected),
        "eligible_cases_at_start": len(cases),
        "improved_cases": win_cases,
        "stage_wins": stage_wins,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "records": records,
    }
    if report_path is not None:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=METHODS,
        default=list(METHODS),
    )
    parser.add_argument("--seconds-per-method", type=float, default=1.0)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    report = run_campaign(
        args.repo_root,
        methods=args.methods,
        seconds_per_method=args.seconds_per_method,
        start_index=args.start_index,
        max_cases=args.max_cases,
        seed=args.seed,
        report_path=args.report,
    )
    print(
        f"campaign: {report['improved_cases']}/{report['selected_cases']} cases, "
        f"{report['stage_wins']} certified stage wins in "
        f"{report['elapsed_seconds']:.2f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

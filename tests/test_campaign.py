from __future__ import annotations

from coverlib.campaign import CampaignCase, improve_case
from coverlib.certificates import balanced_sort_key, certify_schedule


def test_campaign_writes_only_certified_strict_wins(tmp_path):
    blocks = (
        (0, 2, 5),
        (1, 3, 4),
        (0, 1, 3),
        (1, 2, 3),
        (2, 4, 5),
        (1, 3, 5),
        (0, 3, 4),
    )
    certificate = certify_schedule(6, 3, blocks, source="test_input")
    case = CampaignCase(6, 3, blocks, "test_input", certificate)

    improved, wins = improve_case(
        case,
        methods=("residual",),
        seconds_per_method=1.0,
        output_dir=tmp_path,
    )

    assert wins
    assert balanced_sort_key(6, 3, improved.blocks) < balanced_sort_key(
        6,
        3,
        blocks,
    )
    assert certify_schedule(6, 3, improved.blocks).complete
    written = list(tmp_path.glob("v6_k3_b7_*.txt"))
    assert len(written) == 1

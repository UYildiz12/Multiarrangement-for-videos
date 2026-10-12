import inspect
from pathlib import Path

import pytest

import multiarrangement as ma


def test_auto_detect_stimuli_counts_mixed_media(tmp_path: Path):
    for name in ("clip.mp4", "sound.wav", "frame.png", "notes.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    assert ma.auto_detect_stimuli(str(tmp_path)) == 3


def test_create_batches_loads_existing_file(tmp_path: Path):
    batch_file = tmp_path / "batches.txt"
    batch_file.write_text("0,1,2\n1,2,3\n", encoding="utf-8")

    assert ma.create_batches(batch_file) == [[0, 1, 2], [1, 2, 3]]


def test_create_batches_requires_batch_size_for_integer_input():
    with pytest.raises(ValueError, match="batch_size is required"):
        ma.create_batches(12)


def test_create_batches_forwards_schedule_presentation_options(monkeypatch):
    from multiarrangement.core.batch_generator import BatchGenerator

    captured = {}
    fano = [
        [0, 1, 2],
        [0, 3, 4],
        [0, 5, 6],
        [1, 3, 5],
        [1, 4, 6],
        [2, 3, 6],
        [2, 4, 5],
    ]

    def fake_optimize(self, algorithm="balanced", **kwargs):
        captured.update({"algorithm": algorithm, **kwargs})
        return fano

    monkeypatch.setattr(BatchGenerator, "optimize_batches", fake_optimize)
    result = ma.create_batches(
        7,
        3,
        algorithm="hybrid",
        optimize_trial_order=False,
        counterbalance=True,
        participant_index=3,
        counterbalance_family_size=8,
    )

    assert result == fano
    assert captured == {
        "algorithm": "hybrid",
        "optimize_trial_order": False,
        "counterbalance": True,
        "participant_index": 3,
        "counterbalance_family_size": 8,
        "durations": None,
        "refine_schedule": False,
    }


def test_adaptive_public_api_exposes_skip_initial_and_alias():
    parameters = inspect.signature(ma.multiarrangement_adaptive).parameters

    assert parameters["skip_initial"].default is False
    assert parameters["skip_first"].default is None

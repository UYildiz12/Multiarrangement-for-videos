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

from __future__ import annotations

import pytest

from coverlib.cache import read_blocks_file


def test_cache_reader_rejects_repeated_items(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("0 0 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="repeated items"):
        read_blocks_file(path, 4, 3)


def test_cache_reader_rejects_duplicate_blocks(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("0 1 2\n2 1 0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="repeated identical blocks"):
        read_blocks_file(path, 4, 3)

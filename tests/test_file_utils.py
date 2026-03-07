"""Tests for packaged asset resolution helpers."""

from pathlib import Path

from multiarrangement.utils.file_utils import (
    resolve_audio_icon_path,
    resolve_packaged_asset,
    resolve_packaged_file,
)


def test_resolve_audio_icon_path_prefers_packaged_copy():
    """Audio icon resolution should stay inside the package tree."""
    path = resolve_audio_icon_path()

    assert path.name == "Audio.png"
    assert path.parent.name == "multiarrangement"


def test_resolve_packaged_file_finds_instruction_image_in_package_data():
    """Instruction media should resolve from packaged data assets."""
    path = resolve_packaged_file("data", "img1.PNG")

    assert path.name == "img1.PNG"
    assert path.parent.name == "data"


def test_resolve_packaged_asset_checks_requested_subdirectories():
    """Generic asset lookup should search each provided package subdirectory."""
    path = resolve_packaged_asset("img1.PNG", ("data", "demovids"))

    assert path.name == "img1.PNG"
    assert path.parent.name == "data"

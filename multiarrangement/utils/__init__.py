"""Utility functions for multiarrangement experiments."""

from typing import TYPE_CHECKING, Any

from .data_processing import DataProcessor
from .file_utils import get_resource_path, load_batches

if TYPE_CHECKING:
    from .video_processing import VideoProcessor


def __getattr__(name: str) -> Any:
    if name == "VideoProcessor":
        from .video_processing import VideoProcessor

        return VideoProcessor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["VideoProcessor", "DataProcessor", "get_resource_path", "load_batches"]

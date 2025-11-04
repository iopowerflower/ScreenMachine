"""
Configuration and settings management for Screen Machine.
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProcessingConfig:
    """Configuration for video processing and image generation."""
    rows: int = 4
    columns: int = 4
    max_screenshot_width: int = 320
    max_screenshot_height: int = 240
    jpg_quality: int = 75
    overwrite_existing: bool = False
    
    # Optional label toggles
    show_title: bool = True
    show_resolution: bool = True
    show_file_size: bool = True
    show_duration: bool = True
    show_codec: bool = False
    show_timestamps: bool = False
    
    def __post_init__(self):
        """Validate configuration values."""
        if self.rows < 1 or self.columns < 1:
            raise ValueError("Rows and columns must be at least 1")
        if not (1 <= self.jpg_quality <= 100):
            raise ValueError("JPG quality must be between 1 and 100")
        if self.max_screenshot_width < 1 or self.max_screenshot_height < 1:
            raise ValueError("Screenshot dimensions must be at least 1 pixel")
    
    @property
    def total_screenshots(self) -> int:
        """Calculate total number of screenshots needed for the grid."""
        return self.rows * self.columns


def get_default_output_dir(input_dir: str) -> str:
    """Get default output directory based on input directory."""
    return input_dir


def ensure_output_dir(output_dir: str) -> str:
    """Ensure output directory exists, create if it doesn't."""
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def get_video_extensions() -> list:
    """Return list of supported video file extensions."""
    return ['.mp4', '.avi', '.wmv', '.mkv', '.mov', '.m4v', '.webm']